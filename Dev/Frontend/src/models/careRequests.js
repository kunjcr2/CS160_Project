import { ApiError } from "./api.js";

// Frontend view models only: these are NOT backend endpoint/payload contracts.
export const HELP_MAX_LENGTH = 300;
export const REQUEST_STATUS = {
  waiting: "Waiting for support",
  in_progress: "In progress",
  resolved: "Resolved",
  submitted: "Submitted for review",
  open: "Waiting for support",
  requested: "Requested",
  ready: "Ready for pickup",
};

export function createDemoCareRequests({ settle, medications, now = Date.now }) {
  const clone = (value) => structuredClone(value);
  const pending = new Map();
  const refills = [];
  const help = [{
    id: "sample-support-request", older_adult_id: "another-demo-user",
    display_name: "Alex (sample)", summary: "I need help finding my appointment details.",
    status: "waiting", created_at: new Date(now()).toISOString(), assigned_to: null,
  }];
  function propose(type, summary, payload) {
    const action = {
      id: crypto.randomUUID(), action_type: type, status: "proposed", summary,
      expires_at: new Date(now() + 300000).toISOString(),
    };
    pending.set(action.id, { action, payload, result: null });
    return clone(action);
  }
  function medicationForRefill(id) {
    const medication = medications.find((item) => item.id === id);
    if (!medication || medication.stopped_at)
      throw new ApiError("Choose an active medication.", 0, "invalid_medication");
    if (!Number.isInteger(medication.refills_remaining) || medication.refills_remaining <= 0)
      throw new ApiError("A refill cannot be requested for this medication. Contact your doctor.", 0, "refill_unavailable");
    return medication;
  }
  return {
    careRequests: { help: true, refills: true, queue: true, helpHistory: true },
    ownsCareRequest: (id) => pending.has(id),
    async proposeHumanHelp(olderAdultId, summary) {
      await settle();
      const clean = typeof summary === "string" ? summary.trim() : "";
      if (!olderAdultId || clean.length > HELP_MAX_LENGTH)
        throw new ApiError("Use a summary of 300 characters or fewer.");
      if (help.some((row) => row.older_adult_id === olderAdultId && row.status !== "resolved"))
        throw new ApiError("You already have an open help request.", 409, "already_requested");
      return propose("demo_request_help", clean ? `Share this summary with sample support: “${clean}”?` : "Ask sample support for help without sharing a summary?",
        { older_adult_id: olderAdultId, summary: clean });
    },
    async proposeRefill(olderAdultId, medicationId) {
      await settle();
      if (!olderAdultId) throw new ApiError("Choose an older adult first.");
      const med = medicationForRefill(medicationId);
      if (refills.some((row) => row.older_adult_id === olderAdultId && row.medication_id === med.id))
        throw new ApiError("A sample request for this medication is already awaiting review.", 0, "already_requested");
      return propose("demo_request_refill", `Request a sample refill of ${med.name}, ${med.dosage}?`,
        { older_adult_id: olderAdultId, medication_id: med.id, medication_name: med.name, dosage: med.dosage });
    },
    // Called after the parent demo adapter's failure simulation/delay.
    async resolveCareRequest(id, decision) {
      const item = pending.get(id);
      if (!item || !["confirm", "cancel"].includes(decision)) throw new ApiError("Request not found.", 404);
      const status = decision === "confirm" ? "executed" : "cancelled";
      if (item.result) {
        if (item.result.status !== status) throw new ApiError("This request has already changed.", 409);
        return clone(item.result);
      }
      if (decision === "confirm" && now() >= Date.parse(item.action.expires_at))
        throw new ApiError("This proposal has expired. Review a new request.", 410, "expired");
      const isHelp = item.action.action_type === "demo_request_help";
      if (decision === "confirm") {
        if (!isHelp) {
          const medication = medicationForRefill(item.payload.medication_id);
          if (refills.some((row) => row.older_adult_id === item.payload.older_adult_id && row.medication_id === item.payload.medication_id))
            throw new ApiError("A sample request is already awaiting review.", 409);
          medication.refills_remaining -= 1;
        }
        if (isHelp && help.some((row) => row.older_adult_id === item.payload.older_adult_id && row.status !== "resolved"))
          throw new ApiError("You already have an open help request.", 409, "already_requested");
        const row = { id, ...item.payload, created_at: new Date(now()).toISOString(),
          status: isHelp ? "waiting" : "submitted" };
        if (isHelp) help.unshift({ ...row, display_name: "Margaret (sample)", assigned_to: null });
        else refills.unshift(row);
      }
      item.result = { status, message: decision === "cancel"
        ? "Cancelled. No request was submitted."
        : isHelp ? "Sample help request added to the demo queue. No real support agent was contacted."
        : "Sample refill submitted for review. No pharmacy was contacted or refill approved." };
      return clone(item.result);
    },
    async listHelpRequests(olderAdultId) {
      await settle();
      return clone(help.filter((row) => row.older_adult_id === olderAdultId));
    },
    async listRefillRequests(olderAdultId) {
      await settle();
      return clone(refills.filter((row) => row.older_adult_id === olderAdultId));
    },
    async listSupportQueue() { await settle(); return clone(help); },
    async updateSupportRequest(id, expectedStatus, nextStatus) {
      await settle();
      const row = help.find((item) => item.id === id);
      if (!row) throw new ApiError("Request not found.", 404);
      if (row.status !== expectedStatus)
        throw new ApiError("This request has changed. Refresh the queue.", 409);
      if (!((row.status === "waiting" && nextStatus === "in_progress") ||
        (row.status === "in_progress" && nextStatus === "resolved")))
        throw new ApiError("That status change is not available.", 409);
      row.status = nextStatus;
      row.assigned_to = "Demo agent";
      return clone(row);
    },
  };
}
