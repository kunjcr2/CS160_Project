import { Pill, CalendarDays, Check, X } from "lucide-react";
import { formatWhen } from "../../models/reminders.js";

const labels = {
  sent: "Due",
  scheduled: "Upcoming",
  taken: "Taken",
  missed: "Missed",
  acknowledged: "Acknowledged",
  cancelled: "Cancelled",
  failed: "Delivery failed",
};

export default function ReminderBanner({ reminder, busy, disabled, onAnswer }) {
  const medication = reminder.kind === "medication_reminder";
  const Icon = medication ? Pill : CalendarDays;
  return (
    <article
      className={`reminder reminder--${reminder.status}`}
      aria-label={medication ? "Medication reminder" : "Appointment reminder"}
    >
      <div className="reminder-heading">
        <span
          className={`reminder-icon ${medication ? "medication" : "appointment"}`}
        >
          <Icon size={24} aria-hidden="true" />
        </span>
        <span className="status-label">{labels[reminder.status]}</span>
      </div>
      <h3>
        {medication
          ? reminder.medication_name || "Medication reminder"
          : reminder.title || "Appointment reminder"}
      </h3>
      {medication && reminder.dosage && (
        <p className="dosage">{reminder.dosage}</p>
      )}
      <p className="reminder-message">{reminder.message}</p>
      <time dateTime={reminder.due_at}>{formatWhen(reminder.due_at)}</time>
      {reminder.status === "sent" && (
        <div className="button-row">
          {medication ? (
            <>
              <button
                className="primary"
                disabled={disabled}
                onClick={() => onAnswer(reminder, "taken")}
              >
                <Check size={21} aria-hidden="true" />
                {busy ? "Saving..." : "Taken"}
              </button>
              <button
                className="secondary"
                title="I'm skipping this dose"
                disabled={disabled}
                onClick={() => onAnswer(reminder, "missed")}
              >
                <X size={21} aria-hidden="true" />
                Missed
              </button>
            </>
          ) : (
            <button
              className="primary"
              disabled={disabled}
              onClick={() => onAnswer(reminder, "acknowledged")}
            >
              <Check size={21} aria-hidden="true" />
              {busy ? "Saving..." : "OK"}
            </button>
          )}
        </div>
      )}
    </article>
  );
}
