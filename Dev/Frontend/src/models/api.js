import { normalizeNotifications, normalizeReminder } from "./reminders.js";
import { withAuthLock } from "./authLock.js";

export class ApiError extends Error {
  constructor(message, status = 0, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

export function errorMessage(error) {
  if (error.code) return error.message;
  if (error.status === 401 || error.status === 403)
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
  // PR #5 returns intent, not a persisted action. Never invent an action ID.
  if (
    !payload.pending_action &&
    ["appointment", "medication_reminder"].includes(proposal?.kind)
  ) {
    proposal = null;
    notice =
      "This request is not ready to confirm. No appointment or reminder has been saved.";
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
  return { text, proposal, notice, conversation_id: payload.conversation_id };
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
    async converse(text) {
      return normalizeReply(
        await request("/api/v1/ai/process", {
          method: "POST",
          body: { text, language: "en" },
          timeoutMs: 60000,
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
    async resolveAction(id, decision) {
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
      if (status === "failed")
        throw new ApiError(result.message, 409, "action_failed");
      if (status !== (decision === "confirm" ? "executed" : "cancelled"))
        throw new ApiError(
          "We couldn't verify the result. Refresh before trying again.",
        );
      return { status, message: result.message };
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
