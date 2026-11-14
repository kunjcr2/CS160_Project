import { ApiError } from "./api.js";
import { reminderKey } from "./reminders.js";

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
  let failNext = false;
  async function settle() {
    await delay();
    if (failNext) {
      failNext = false;
      throw new ApiError("We couldn't connect. Please try again.");
    }
  }
  return {
    mode: "demo",
    async converse(text) {
      await settle();
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
      if (actions.get(id) !== "pending")
        throw new ApiError("This action has already changed.", 409);
      const status = decision === "confirm" ? "executed" : "cancelled";
      actions.set(id, status);
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
