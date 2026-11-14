import { useEffect, useState } from "react";
import { CalendarDays, Check, X } from "lucide-react";
import { formatWhen } from "../../models/reminders.js";

export default function ConfirmationCard({ proposal, busy, onResolve }) {
  const [now, setNow] = useState(Date.now());
  const expires = proposal.expires_at ? Date.parse(proposal.expires_at) : null;
  const expired =
    expires !== null && (!Number.isFinite(expires) || now >= expires);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [proposal.id]);
  const details = proposal.details ?? {};
  return (
    <section className="confirmation" aria-labelledby="confirmation-title">
      <p className="eyebrow">
        <CalendarDays size={20} aria-hidden="true" />
        REVIEW APPOINTMENT
      </p>
      <h3 id="confirmation-title">{proposal.summary}</h3>
      <dl>
        {Object.entries(details)
          .filter(([, value]) => ["string", "number"].includes(typeof value))
          .map(([key, value]) => (
            <div key={key}>
              <dt>{key.replaceAll("_", " ")}</dt>
              <dd>
                {typeof value === "string" && /^\d{4}-\d{2}-\d{2}T/.test(value)
                  ? formatWhen(value)
                  : String(value)}
              </dd>
            </div>
          ))}
      </dl>
      {expired && (
        <p role="status">
          This proposal has expired. Cancel it and request a new appointment.
        </p>
      )}
      <div className="button-row">
        <button
          className="primary"
          disabled={Boolean(busy) || expired}
          onClick={() => onResolve("confirm")}
        >
          <Check size={22} aria-hidden="true" />
          {busy === "confirm" ? "Confirming..." : "Confirm"}
        </button>
        <button
          className="secondary"
          disabled={Boolean(busy)}
          onClick={() => onResolve("cancel")}
        >
          <X size={22} aria-hidden="true" />
          {busy === "cancel" ? "Cancelling..." : "Cancel"}
        </button>
      </div>
    </section>
  );
}
