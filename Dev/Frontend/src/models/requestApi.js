import { ApiError } from "./api.js";
import { HELP_MAX_LENGTH } from "./careRequests.js";

const id = (value) => typeof value === "string" && value.trim().length > 0;
const date = (value) => typeof value === "string" && Number.isFinite(Date.parse(value));
const invalid = () => new ApiError("The service returned an incomplete request. Refresh before continuing.");

export function normalizeAssistance(row) {
  if (!row || !id(row.id) || !id(row.older_adult_id) || !id(row.older_adult_name) ||
      !["open", "in_progress", "resolved"].includes(row.status) || !date(row.created_at) ||
      !(row.summary === null || typeof row.summary === "string") ||
      !(row.assigned_to_name === null || typeof row.assigned_to_name === "string")) throw invalid();
  return { ...row, display_name: row.older_adult_name, assigned_to: row.assigned_to_name };
}

export function normalizeRefills(rows) {
  if (!Array.isArray(rows)) throw invalid();
  return rows.map((row) => {
    if (!row || !id(row.id) || !id(row.medication?.id) || !id(row.medication.name) ||
        !id(row.medication.dosage) || !Number.isInteger(row.medication.refills_remaining) ||
        row.medication.refills_remaining < 0 || !["requested", "in_progress", "ready"].includes(row.status) ||
        !id(row.status_message) || !date(row.created_at)) throw invalid();
    return { ...row, medication_id: row.medication.id,
      medication_name: row.medication.name, dosage: row.medication.dosage };
  }).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
}

export function createRequestApi(request, normalizeAction) {
  async function propose(actionType, payload) {
    const action = normalizeAction(await request("/api/v1/actions", {
      method: "POST", body: { action_type: actionType, payload },
    }));
    if (action.action_type !== actionType) throw invalid();
    return action;
  }
  return {
    careRequests: { help: true, refills: true, queue: true, helpHistory: false },
    async proposeHumanHelp(olderAdultId, summary = "", reason = "user_request") {
      if (!id(olderAdultId) || typeof summary !== "string" || summary.trim().length > HELP_MAX_LENGTH ||
          !["user_request", "repeated_failures"].includes(reason))
        throw new ApiError("Use a summary of 300 characters or fewer.");
      return propose("request_help", { older_adult_id: olderAdultId, summary: summary.trim(), reason });
    },
    async proposeRefill(olderAdultId, medicationId) {
      if (!id(olderAdultId) || !id(medicationId)) throw new ApiError("Choose a medication first.");
      return propose("request_refill", { older_adult_id: olderAdultId, medication_id: medicationId });
    },
    async listRefillRequests(olderAdultId, signal) {
      if (!id(olderAdultId)) throw invalid();
      return normalizeRefills(await request(`/api/v1/older-adults/${encodeURIComponent(olderAdultId)}/refills`, { signal }));
    },
    async listSupportQueue(_userId, signal) {
      const rows = await request("/api/v1/assistance/queue", { signal });
      if (!Array.isArray(rows)) throw invalid();
      return rows.map(normalizeAssistance).filter((row) => row.status !== "resolved")
        .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));
    },
    async updateSupportRequest(requestId, _expectedStatus, status) {
      if (!id(requestId) || !["in_progress", "resolved"].includes(status)) throw invalid();
      // The backend locks the row and arbitrates concurrent claims. It does not
      // accept a client-side expected_status or an agent ID.
      const row = normalizeAssistance(await request(`/api/v1/assistance/${encodeURIComponent(requestId)}`, {
        method: "PATCH", body: { status },
      }));
      if (row.id !== requestId || row.status !== status) throw invalid();
      return row;
    },
    async proposeCancellation(appointmentId) {
      if (!id(appointmentId)) throw invalid();
      return propose("cancel_appointment", { appointment_id: appointmentId });
    },
    async proposeReschedule(appointmentId, slotId) {
      if (!id(appointmentId) || !id(slotId)) throw invalid();
      return propose("reschedule_appointment", { appointment_id: appointmentId, slot_id: slotId });
    },
  };
}
