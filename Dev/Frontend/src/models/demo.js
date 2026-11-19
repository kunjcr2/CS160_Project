import { ApiError } from "./api.js";
import { reminderKey } from "./reminders.js";
import { createDemoCareRequests } from "./careRequests.js";

const delay = () => new Promise((resolve) => setTimeout(resolve, 450));
const copy = (value) => structuredClone(value);

export function createDemoApi() {
  const today = new Date();
  today.setHours(8, 0, 0, 0);
  const tomorrow = new Date(today);
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(10, 30);
  let rows = [
    {
      id: "demo-dose-1",
      notification_id: "demo-notice-1",
      kind: "medication_reminder",
      medication_name: "Lisinopril",
      dosage: "10 mg",
      due_at: today.toISOString(),
      status: "sent",
      message: "Time to take your Lisinopril, 10 mg.",
    },
    {
      id: "demo-visit-1",
      notification_id: "demo-notice-2",
      kind: "appointment_reminder",
      due_at: today.toISOString(),
      status: "sent",
      message: "Your appointment with Dr. Elena Chen is tomorrow at 10:30 AM.",
      title: "Appointment reminder",
    },
  ];
  const initial = copy(rows);
  const listeners = new Set();
  const actions = new Map();
  const messageActions = new Map();
  const sentMessages = [];
  const appointments = [];
  const appointmentActions = new Map();
  const demoSlots = new Map();
  const provider = { id: "demo-doctor", name: "Dr. Elena Chen", specialty: "Cardiology", location: "SJSU Health Clinic" };
  async function changeAppointment(type, appointmentId, slotId) {
    await settle();
    const visit = appointments.find((row) => row.id === appointmentId && row.status === "booked");
    if (!visit) throw new ApiError("This appointment is no longer available.", 409);
    const slot = slotId ? demoSlots.get(slotId) : null;
    if (slotId && !slot) throw new ApiError("Choose another available time.", 409);
    const id = crypto.randomUUID();
    actions.set(id, "pending");
    appointmentActions.set(id, { type, appointmentId, slot });
    return { id, action_type: type, status: "proposed", expires_at: new Date(Date.now() + 300000).toISOString(),
      summary: type === "cancel_appointment" ? "Cancel this sample appointment with Dr. Elena Chen?"
        : "Move this sample appointment with Dr. Elena Chen to the selected time?",
      details: { From: visit.starts_at, ...(slot ? { To: slot.starts_at } : {}) } };
  }
  const medications = [
    { id: "demo-medication", name: "Lisinopril", dosage: "10 mg", instructions: null,
      refills_remaining: 2, schedules: [{ time_of_day: "08:00:00", days_of_week: [0, 1, 2, 3, 4, 5, 6] }] },
    { id: "demo-medication-no-refills", name: "Metformin", dosage: "500 mg", instructions: null,
      refills_remaining: 0, schedules: [] },
  ];
  let failNext = false;
  async function settle() {
    await delay();
    if (failNext) {
      failNext = false;
      throw new ApiError("We couldn't connect. Please try again.");
    }
  }
  const requests = createDemoCareRequests({ settle, medications });
  return {
    mode: "demo",
    ...requests,
    async getPendingAction() {
      return null;
    },
    async listProviders() {
      return [
        {
          id: "demo-doctor",
          name: "Dr. Elena Chen",
          specialty: "Cardiology",
          location: "SJSU Health Clinic",
        },
      ];
    },
    async listSlots(providerId, from) {
      const start = new Date(`${from}T10:30:00`);
      if (start <= new Date()) start.setTime(tomorrow.getTime());
      const slot = {
          slot_id: `demo-slot:${from}`,
          provider,
          starts_at: start.toISOString(),
          ends_at: new Date(start.getTime() + 1800000).toISOString(),
          label: "Sample appointment at 10:30 AM",
      };
      demoSlots.set(slot.slot_id, slot);
      return appointments.some((row) => row.status === "booked" && row.starts_at === slot.starts_at) ? [] : [slot];
    },
    async proposeAppointment(slotId) {
      await settle();
      const id = crypto.randomUUID();
      actions.set(id, "pending");
      appointmentActions.set(id, { type: "book_appointment", slot: demoSlots.get(slotId) });
      return {
        id,
        action_type: "book_appointment",
        summary: "Book a sample appointment with Dr. Elena Chen?",
        status: "proposed",
        expires_at: new Date(Date.now() + 300000).toISOString(),
      };
    },
    async listAppointments() {
      return copy(appointments);
    },
    proposeCancellation: (id) => changeAppointment("cancel_appointment", id),
    proposeReschedule: (id, slotId) => changeAppointment("reschedule_appointment", id, slotId),
    async proposeCareMessage(olderAdultId, providerId, body) {
      await settle();
      const id = crypto.randomUUID();
      const clean = body.trim();
      actions.set(id, "pending");
      messageActions.set(id, { olderAdultId, providerId, body: clean });
      return { id, action_type: "send_care_message", status: "proposed",
        summary: `I will send Dr. Elena Chen: "${clean}". Should I send it?`,
        expires_at: new Date(Date.now() + 300000).toISOString() };
    },
    async listCareMessages() { return copy(sentMessages); },
    async listMedications() {
      return copy(medications);
    },
    async listMedicationReminders() {
      return copy(rows.filter((row) => row.kind === "medication_reminder"));
    },
    async converse(text) {
      await settle();
      if (/\b(refill|help|support)\b/i.test(text)) return { text: "Let's review the details before submitting anything.",
        proposal: null, intent: { kind: /\brefill\b/i.test(text) ? "refill" : "human_help" } };
      if (/\b(appointment|doctor|book|visit)\b/i.test(text)) {
        const proposal = {
          id: crypto.randomUUID(),
          type: "book_appointment",
          summary: "Book an appointment with Dr. Elena Chen",
          details: {
            Doctor: "Dr. Elena Chen",
            When: tomorrow.toISOString(),
            Location: "SJSU Health Clinic, Room 204",
          },
          expires_at: new Date(Date.now() + 10 * 60000).toISOString(),
        };
        actions.set(proposal.id, "pending");
        return {
          text: "Here is a sample appointment to review. Would you like to confirm it?",
          proposal,
        };
      }
      if (/\b(remind|reminder|medication|taken|missed|took)\b/i.test(text))
        return {
          text: "Your sample reminders are listed in Today. You can record Taken or Missed on a medication reminder, or acknowledge an appointment with OK.",
          proposal: null,
        };
      return {
        text: "Hello. Would you like to review an appointment or check your reminders?",
        proposal: null,
      };
    },
    async resolveAction(id, decision) {
      await settle();
      if (requests.ownsCareRequest(id)) return requests.resolveCareRequest(id, decision);
      if (actions.get(id) !== "pending")
        throw new ApiError("This action has already changed.", 409);
      const status = decision === "confirm" ? "executed" : "cancelled";
      actions.set(id, status);
      if (messageActions.has(id)) {
        const message = messageActions.get(id);
        if (decision === "confirm") sentMessages.unshift({
          id: crypto.randomUUID(), provider: { id: message.providerId, name: "Dr. Elena Chen" },
          body: message.body, status: "sent", created_at: new Date().toISOString(),
        });
        return { status, message: decision === "confirm"
          ? "Sample message sent. Nothing was delivered to a real doctor."
          : "Cancelled. No message was sent." };
      }
      const change = appointmentActions.get(id);
      if (decision === "confirm") {
        if (change?.appointmentId) {
          const previous = appointments.find((row) => row.id === change.appointmentId);
          if (previous) previous.status = "cancelled";
        }
        if (change?.type !== "cancel_appointment") appointments.unshift({
          id: crypto.randomUUID(), provider, location: provider.location, status: "booked",
          starts_at: change?.slot?.starts_at || tomorrow.toISOString(),
          ends_at: change?.slot?.ends_at || new Date(tomorrow.getTime() + 1800000).toISOString(),
        });
      }
      if (change && change.type !== "book_appointment") return { status,
        message: decision === "confirm" ? `Sample appointment ${change.type === "cancel_appointment" ? "cancelled" : "rescheduled"}. No real provider was contacted.` : "Cancelled. The original appointment was kept." };
      return {
        status,
        message:
          decision === "confirm"
            ? "Sample appointment confirmed. Nothing was booked with a real provider."
            : "Cancelled. No appointment was booked.",
      };
    },
    async listNotifications() {
      await settle();
      return copy(rows);
    },
    async answerReminder(reminder, answer) {
      await settle();
      const row = rows.find(
        (item) => reminderKey(item) === reminderKey(reminder),
      );
      if (!row) throw new ApiError("Reminder not found.", 404);
      if (row.status !== "sent") throw new ApiError("Already answered.", 409);
      row.status = answer;
      listeners.forEach((fn) => fn());
      return copy(row);
    },
    subscribe(onChange, onState) {
      listeners.add(onChange);
      onState("demo");
      return () => listeners.delete(onChange);
    },
    simulateMissed() {
      rows = rows.map((row) =>
        row.kind === "medication_reminder" && row.status === "sent"
          ? { ...row, status: "missed" }
          : row,
      );
      listeners.forEach((fn) => fn());
    },
    resetReminders() {
      rows = copy(initial);
      listeners.forEach((fn) => fn());
    },
    failNextRequest() {
      failNext = true;
    },
  };
}
