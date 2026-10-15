export const MEDICATION_STATUSES = [
  "scheduled",
  "sent",
  "taken",
  "missed",
  "cancelled",
  "failed",
];
export const APPOINTMENT_STATUSES = [
  "scheduled",
  "sent",
  "acknowledged",
  "cancelled",
  "failed",
];

export function formatWhen(value, timeZone) {
  const date = new Date(value);
  if (!value || Number.isNaN(date.getTime())) return "Time unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
    ...(timeZone ? { timeZone } : {}),
  }).format(date);
}

export function normalizeReminder(value, kind = "medication_reminder") {
  const statuses =
    kind === "medication_reminder" ? MEDICATION_STATUSES : APPOINTMENT_STATUSES;
  if (
    !value ||
    typeof value.id !== "string" ||
    !value.id ||
    typeof value.message !== "string" ||
    !value.message.trim() ||
    !statuses.includes(value.status) ||
    typeof value.due_at !== "string" ||
    Number.isNaN(Date.parse(value.due_at))
  ) {
    throw new Error(
      "The reminder response is incomplete. Please refresh and try again.",
    );
  }
  return { ...value, kind };
}

// Notification IDs and medication reminder IDs are not interchangeable.
// This envelope is provisional until the notification owner confirms the schema.
export function normalizeNotifications(payload) {
  const rows = Array.isArray(payload) ? payload : payload?.notifications;
  if (!Array.isArray(rows))
    throw new Error("The notification response has an unexpected format.");
  return rows
    .filter((row) =>
      ["medication_reminder", "appointment_reminder"].includes(row?.kind),
    )
    .map((row) => {
      const data = row.payload ?? row;
      const reminderId =
        row.reminder_id ?? (row.payload ? row.payload.id : null);
      if (typeof row.id !== "string" || !reminderId) {
        throw new Error(
          "A notification is missing its reminder ID. Please refresh and try again.",
        );
      }
      return {
        ...normalizeReminder({ ...data, id: reminderId }, row.kind),
        notification_id: row.id,
      };
    });
}

export function reminderKey(reminder) {
  return `${reminder.kind}:${reminder.id}`;
}

export function mergeReminders(current, updates) {
  const byId = new Map(current.map((item) => [reminderKey(item), item]));
  for (const item of updates) byId.set(reminderKey(item), item);
  return [...byId.values()].sort(
    (a, b) => Date.parse(a.due_at) - Date.parse(b.due_at),
  );
}
