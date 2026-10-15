import { normalizeNotifications, normalizeReminder } from "./reminders.js";

export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.status = status;
  }
}

export function errorMessage(error) {
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
  const proposal = payload.pending_action ?? payload.proposal ?? null;
  if (
    proposal &&
    (typeof proposal.id !== "string" || typeof proposal.summary !== "string")
  ) {
    throw new ApiError(
      "The proposal is incomplete. Please ask the assistant to try again.",
    );
  }
  return { text, proposal, conversation_id: payload.conversation_id };
}

export function createApi({
  notificationsPath = "/notifications",
  streamPath = "",
  getAccessToken = () => null,
  fetchImpl = fetch,
} = {}) {
  async function request(path, { method = "GET", body, signal } = {}) {
    const timeout = AbortSignal.timeout(15000);
    const token = getAccessToken();
    let response;
    try {
      response = await fetchImpl(path, {
        method,
        credentials: "include",
        headers: {
          Accept: "application/json",
          ...(body ? { "Content-Type": "application/json" } : {}),
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
        signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw new ApiError(
        timeout.aborted
          ? "The request timed out. Refresh before trying again."
          : "We couldn't connect. Check your connection and try again.",
      );
    }
    if (!response.ok)
      throw new ApiError(
        "The service couldn't complete the request. Please try again.",
        response.status,
      );
    if (!response.headers.get("content-type")?.includes("application/json"))
      throw new ApiError("The service returned an unexpected response.");
    try {
      return await response.json();
    } catch {
      throw new ApiError("The service returned an unreadable response.");
    }
  }

  return {
    mode: "live",
    async converse(text, conversationId) {
      return normalizeReply(
        await request("/api/v1/ai/process", {
          method: "POST",
          body: {
            text,
            ...(conversationId ? { conversation_id: conversationId } : {}),
          },
        }),
      );
    },
    async resolveAction(id, decision) {
      if (!["confirm", "cancel"].includes(decision))
        throw new ApiError("Invalid action.");
      const result = await request(
        `/api/v1/actions/${encodeURIComponent(id)}/${decision}`,
        { method: "POST" },
      );
      const expected = decision === "confirm" ? "executed" : "cancelled";
      if (result.status !== expected || typeof result.message !== "string")
        throw new ApiError(
          "We couldn't verify the result. Refresh before trying again.",
        );
      return result;
    },
    async listNotifications(signal) {
      return normalizeNotifications(
        await request(notificationsPath, { signal }),
      );
    },
    async answerReminder(reminder, answer) {
      if (reminder.kind === "medication_reminder") {
        if (!["taken", "missed"].includes(answer))
          throw new ApiError("Invalid reminder response.");
        const updated = normalizeReminder(
          await request(
            `/api/v1/medication-reminders/${encodeURIComponent(reminder.id)}/${answer}`,
            { method: "POST" },
          ),
        );
        if (updated.id !== reminder.id || updated.status !== answer)
          throw new ApiError(
            "The reminder changed. Refresh to check its status.",
          );
        return { ...updated, notification_id: reminder.notification_id };
      }
      if (answer !== "acknowledged" || !reminder.notification_id)
        throw new ApiError("Invalid reminder response.");
      // Appointment acknowledgement's response format is not confirmed yet.
      await request(
        `${notificationsPath}/${encodeURIComponent(reminder.notification_id)}/ack`,
        { method: "POST" },
      );
      const rows = await this.listNotifications();
      const updated = rows.find(
        (item) => item.id === reminder.id && item.kind === reminder.kind,
      );
      if (!updated || updated.status !== "acknowledged")
        throw new ApiError(
          "We couldn't verify the acknowledgement. Please refresh.",
        );
      return updated;
    },
    subscribe(onChange, onState) {
      if (!streamPath) {
        onState("manual");
        return () => {};
      }
      // Enable only after agreeing on SSE URL, cookie authentication and event format.
      const stream = new EventSource(streamPath, { withCredentials: true });
      const update = () => onChange();
      stream.onopen = () => {
        onState("connected");
        onChange();
      };
      stream.onmessage = update;
      stream.addEventListener("notification", update);
      stream.addEventListener("reminder_updated", update);
      stream.onerror = () => onState("reconnecting");
      onState("connecting");
      return () => stream.close();
    },
  };
}
