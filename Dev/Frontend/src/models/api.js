import { normalizeNotifications, normalizeReminder } from "./reminders.js";
import { withAuthLock } from "./authLock.js";
import { MESSAGE_MAX_LENGTH, normalizeCareMessages } from "./careMessages.js";
import { createRequestApi } from "./requestApi.js";

export class ApiError extends Error {
  constructor(message, status = 0, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function errorMessage(error) {
  if (error.code) return error.message;
  if (error.status === 403) return "Your account does not have access to this service.";
  if (error.status === 401)
    return "Please sign in again before continuing.";
  if (error.status === 404)
    return "This item or service is unavailable. Refresh to check again.";
  if (error.status === 409)
    return "This item has already changed. Refresh to see its latest status.";
  if (error.status === 429)
    return "There are too many requests. Please try again shortly.";
  return error.message || "Something went wrong. Please try again.";
}

export function normalizeReply(payload) {
  const text = payload?.reply ?? payload?.response ?? payload?.text;
  if (typeof text !== "string" || !text.trim())
    throw new ApiError(
      "The assistant returned an unreadable reply. Please try again.",
    );
  let proposal = payload.pending_action ?? payload.proposal ?? null;
  let notice = "";
  let intent = null;
  // PR #5 returns intent, not a persisted action. Never invent an action ID.
  if (
    !payload.pending_action &&
    ["appointment", "medication_reminder", "refill", "human_help"].includes(proposal?.kind)
  ) {
    const kind = proposal.kind;
    intent = { ...proposal };
    proposal = null;
    notice = kind === "refill" || kind === "human_help"
      ? `Open ${kind === "refill" ? "Prescription refills" : "Help"} in My care to check availability. No request has been submitted.`
      : "This request is not ready to confirm. No appointment or reminder has been saved.";
  }
  if (proposal) {
    proposal = {
      ...proposal,
      summary: proposal.summary_text ?? proposal.summary,
    };
    if (
      typeof proposal.id !== "string" ||
      !proposal.id ||
      typeof proposal.summary !== "string"
    )
      throw new ApiError(
        "The proposal is incomplete. Please ask the assistant to try again.",
      );
  }
  return { text, proposal, notice, intent,
    offerHumanHelp: payload.offer_human_help === true,
    unclearTurns: Number.isInteger(payload.unclear_turns) ? Math.max(0, Math.min(3, payload.unclear_turns)) : 0,
    conversation_id: payload.conversation_id };
}

export function normalizeAction(action) {
  if (
    !action ||
    typeof action.id !== "string" ||
    !action.id ||
    typeof action.summary_text !== "string" ||
    !action.summary_text.trim() ||
    action.status !== "proposed" ||
    !Number.isFinite(Date.parse(action.expires_at))
  )
    throw new ApiError(
      "The confirmation response is incomplete. Please refresh before continuing.",
    );
  return { ...action, summary: action.summary_text };
}

function listResponse(value) {
  if (!Array.isArray(value))
    throw new ApiError("The service returned an unexpected list.");
  return value;
}

export function createApi({
  notificationsPath = "/api/v1/notifications",
  getAccessToken = () => null,
  onUnauthorized = () => {},
  fetchImpl = fetch,
  pollInterval = 20000,
} = {}) {
  // undefined permits an injected initial token; null explicitly clears it.
  let accessToken;
  let refreshing = null;
  let sessionVersion = 0;
  const currentToken = () =>
    accessToken === undefined ? getAccessToken() : accessToken;

  function checkSession(version) {
    if (version !== sessionVersion)
      throw new ApiError(
        "Your session changed. Please try again.",
        401,
        "session_changed",
      );
  }

  function expireSession(version) {
    if (version !== sessionVersion) return;
    sessionVersion++;
    accessToken = null;
    onUnauthorized();
  }

  function acceptToken(result) {
    if (typeof result?.access_token !== "string" || !result.access_token)
      throw new ApiError("The sign-in response is incomplete.");
    accessToken = result.access_token;
  }

  async function refreshToken() {
    if (!refreshing) {
      const version = sessionVersion;
      refreshing = withAuthLock(async () => {
        checkSession(version);
        const result = await request("/api/v1/auth/refresh", {
          method: "POST",
        });
        checkSession(version);
        acceptToken(result);
      }).finally(() => {
        refreshing = null;
      });
    }
    return refreshing;
  }

  async function request(
    path,
    { method = "GET", body, signal, audio = false, timeoutMs = 15000 } = {},
    retried = false,
  ) {
    signal?.throwIfAborted();
    const version = sessionVersion;
    const timeout = AbortSignal.timeout(timeoutMs);
    const token = currentToken();
    const authRequest = path.startsWith("/api/v1/auth/");
    const multipart = body instanceof FormData;
    let response;
    try {
      response = await fetchImpl(path, {
        method,
        credentials: "include",
        headers: {
          Accept: audio ? "audio/mpeg" : "application/json",
          ...(body && !multipart ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(body ? { body: multipart ? body : JSON.stringify(body) } : {}),
        signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(
        timeout.aborted
          ? "The request timed out. Please try again."
          : "We couldn't connect. Check your connection and try again.",
      );
    }
    signal?.throwIfAborted();
    if (!authRequest) checkSession(version);
    if (response.status === 401 && !authRequest && token) {
      if (!retried) {
        try {
          // Another request may have refreshed before this old 401 arrived.
          if (token === currentToken()) await refreshToken();
        } catch (error) {
          // A network failure or 5xx does not prove the session has expired.
          if (error.status === 401) expireSession(version);
          throw error;
        }
        signal?.throwIfAborted();
        checkSession(version);
        return request(path, { method, body, signal, audio, timeoutMs }, true);
      }
      expireSession(version);
    }
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      const detail = data?.detail;
      throw new ApiError(
        typeof detail === "string"
          ? detail
          : detail?.message ||
            "The service couldn't complete the request. Please try again.",
        response.status,
        typeof detail?.code === "string" ? detail.code : "",
      );
    }
    if (response.status === 204) return null;
    if (audio) {
      if (!response.headers.get("content-type")?.includes("audio/mpeg"))
        throw new ApiError(
          "The speech service returned an unexpected response.",
        );
      const blob = await response.blob();
      signal?.throwIfAborted();
      if (!authRequest) checkSession(version);
      if (!blob.size)
        throw new ApiError("The speech service returned empty audio.");
      return blob;
    }
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError("The service returned an unexpected response.");
    let result;
    try {
      result = await response.json();
    } catch {
      throw new ApiError("The service returned an unreadable response.");
    }
    signal?.throwIfAborted();
    if (!authRequest) checkSession(version);
    return result;
  }

  return {
    mode: "live",
    ...createRequestApi(request, normalizeAction),
    async restoreSession() {
      await refreshToken();
      return request("/api/v1/users/me");
    },
    async signIn(method, values) {
      await withAuthLock(async () => {
        const result = await request(
          `/api/v1/auth/${method === "pair" ? "pair" : "login"}`,
          { method: "POST", body: values },
        );
        acceptToken(result);
        sessionVersion++;
      });
      return request("/api/v1/users/me");
    },
    async signOut() {
      await withAuthLock(async () => {
        await request("/api/v1/auth/logout", { method: "POST" });
        accessToken = null;
        sessionVersion++;
      });
    },
    async converse(text, _conversationId, unclearTurns = 0) {
      return normalizeReply(
        await request("/api/v1/ai/process", {
          method: "POST",
          body: { text, language: "en", unclear_turns: unclearTurns },
          timeoutMs: 60000,
        }),
      );
    },
    async getPendingAction(signal) {
      const result = await request("/api/v1/actions/pending", { signal });
      if (result?.action === null) return null;
      return normalizeAction(result?.action);
    },
    async proposeAppointment(slotId) {
      return normalizeAction(
        await request("/api/v1/actions", {
          method: "POST",
          body: {
            action_type: "book_appointment",
            payload: { slot_id: slotId },
          },
        }),
      );
    },
    async listProviders(signal) {
      return listResponse(await request("/api/v1/providers", { signal }));
    },
    async proposeCareMessage(olderAdultId, providerId, body) {
      const clean = typeof body === "string" ? body.trim() : "";
      if (!olderAdultId || !providerId || !clean || clean.length > MESSAGE_MAX_LENGTH)
        throw new ApiError("Choose a doctor and enter a message of 1–2,000 characters.");
      const action = normalizeAction(await request("/api/v1/actions", {
        method: "POST",
        body: { action_type: "send_care_message", payload: {
          older_adult_id: olderAdultId, provider_id: providerId, body: clean,
        } },
      }));
      if (action.action_type !== "send_care_message")
        throw new ApiError("We couldn't verify the message proposal. Refresh before continuing.");
      return action;
    },
    async listCareMessages(olderAdultId, signal) {
      return normalizeCareMessages(await request(
        `/api/v1/older-adults/${encodeURIComponent(olderAdultId)}/messages`, { signal },
      ));
    },
    async listSlots(providerId, from, to, signal) {
      const query = new URLSearchParams({
        provider_id: providerId,
        from,
        to,
        limit: "20",
      });
      return listResponse(await request(`/api/v1/slots?${query}`, { signal }));
    },
    async listAppointments(signal) {
      return listResponse(await request("/api/v1/appointments", { signal }));
    },
    async listMedications(userId, signal) {
      return listResponse(
        await request(
          `/api/v1/older-adults/${encodeURIComponent(userId)}/medications`,
          { signal },
        ),
      );
    },
    async listMedicationReminders(userId, date, signal) {
      const query = new URLSearchParams({ date });
      const rows = listResponse(
        await request(
          `/api/v1/older-adults/${encodeURIComponent(userId)}/medication-reminders?${query}`,
          { signal },
        ),
      );
      // The daily-dose endpoint intentionally has no message field. Display the
      // prescribed name/dosage as a neutral label, not an instruction to take it.
      return rows.map((row) =>
        normalizeReminder({
          ...row,
          message: `${row.medication_name}, ${row.dosage}`,
        }),
      );
    },
    async transcribe(blob, signal) {
      const form = new FormData();
      const extension = blob.type.includes("mp4")
        ? "m4a"
        : blob.type.includes("wav")
          ? "wav"
          : "webm";
      form.append("audio", blob, `recording.${extension}`);
      const result = await request("/api/v1/ai/transcribe", {
        method: "POST",
        body: form,
        signal,
        timeoutMs: 60000,
      });
      if (typeof result.text !== "string" || !result.text.trim())
        throw new ApiError("No speech was detected. Please record again.");
      if (result.text.length > 2000)
        throw new ApiError(
          "The recording is too long. Please record a shorter message.",
        );
      return result.text.trim();
    },
    synthesize(text, signal) {
      if (!text.trim() || text.length > 2000)
        throw new ApiError(
          "This reply is too long to play. You can read it in the conversation.",
        );
      return request("/api/v1/ai/tts", {
        method: "POST",
        body: { text },
        signal,
        audio: true,
        timeoutMs: 90000,
      });
    },
    async resolveAction(id, decision, expectedType) {
      if (!["confirm", "cancel"].includes(decision))
        throw new ApiError("Invalid action.");
      const result = await request(
        `/api/v1/actions/${encodeURIComponent(id)}/${decision}`,
        { method: "POST" },
      );
      if (result.action?.id !== id || typeof result.message !== "string")
        throw new ApiError(
          "We couldn't verify the result. Refresh before trying again.",
        );
      const status = result.action.status;
      if (expectedType && result.action.action_type !== expectedType)
        throw new ApiError("We couldn't verify the message result. Refresh before trying again.");
      if (status === "failed")
        throw new ApiError(result.message, 409, "action_failed");
      if (status !== (decision === "confirm" ? "executed" : "cancelled"))
        throw new ApiError(
          "We couldn't verify the result. Refresh before trying again.",
        );
      // PR #34 records an executed command even when its messaging adapter
      // reports delivery failure. Execution alone is not evidence of sending.
      if (decision === "confirm" && result.action.action_type === "send_care_message") {
        if (result.action.result?.ok === false)
          throw new ApiError(result.message, 409, "message_delivery_failed");
        if (result.action.result?.ok !== true || typeof result.action.result?.message_id !== "string" || !result.action.result.message_id)
          throw new ApiError("We couldn't verify whether the message was sent. Retry this confirmation to check the same request.");
      }
      const requiredResult = { request_help: "assistance_request_id", request_refill: "refill_request_id",
        cancel_appointment: "appointment_id", reschedule_appointment: "appointment_id" }[result.action.action_type];
      if (decision === "confirm" && requiredResult &&
          (typeof result.action.result?.[requiredResult] !== "string" || !result.action.result[requiredResult]))
        throw new ApiError("We couldn't verify the saved request. Retry this confirmation to check the same request.");
      return { status, message: result.message, data: result.action.result };
    },
    async listNotifications(signal) {
      return normalizeNotifications(
        await request(notificationsPath, { signal }),
      );
    },
    async answerReminder(reminder, answer) {
      const medication = reminder.kind === "medication_reminder";
      if (
        !(medication ? ["taken", "missed"] : ["acknowledged"]).includes(answer)
      )
        throw new ApiError("Invalid reminder response.");
      const path = medication
        ? `/api/v1/medication-reminders/${encodeURIComponent(reminder.id)}/${answer}`
        : `/api/v1/appointment-reminders/${encodeURIComponent(reminder.id)}/acknowledge`;
      const data = await request(path, { method: "POST" });
      const updated = normalizeReminder(
        { ...data, message: data.message ?? reminder.message },
        reminder.kind,
      );
      if (updated.id !== reminder.id || updated.status !== answer)
        throw new ApiError(
          "The reminder changed. Refresh to check its status.",
        );
      return updated;
    },
    subscribe(onChange, onState) {
      let active = true;
      let timer;
      const tick = async () => {
        try {
          if (globalThis.document?.visibilityState !== "hidden")
            await onChange();
        } finally {
          if (active) timer = setTimeout(tick, pollInterval);
        }
      };
      onState("polling");
      timer = setTimeout(tick, pollInterval);
      return () => {
        active = false;
        clearTimeout(timer);
      };
    },
  };
}
