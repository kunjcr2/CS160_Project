import { useEffect, useRef, useState } from "react";
import { CalendarDays, MessageCircle, Pill, LifeBuoy, Check, X } from "lucide-react";
import { formatWhen } from "../../models/reminders.js";

export default function ConfirmationCard({ proposal, busy, onResolve }) {
  const card = useRef(null);
  const actionType = proposal.action_type ?? proposal.type ?? "book_appointment";
  const isMessage = actionType === "send_care_message";
  const isHelp = ["request_help", "demo_request_help"].includes(actionType);
  const isRefill = ["request_refill", "demo_request_refill"].includes(actionType);
  const Icon = isMessage ? MessageCircle : isHelp ? LifeBuoy : isRefill ? Pill : CalendarDays;
  useEffect(() => { card.current?.focus(); }, [proposal.id]);
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
    <section ref={card} tabIndex={-1} className="confirmation" aria-labelledby="confirmation-title">
      <p className="eyebrow">
        <Icon size={20} aria-hidden="true" />
        {isMessage ? "REVIEW MESSAGE" : isHelp ? "REVIEW HELP REQUEST" : isRefill ? "REVIEW REFILL" : actionType === "cancel_appointment" ? "REVIEW CANCELLATION" : actionType === "reschedule_appointment" ? "REVIEW RESCHEDULE" : actionType === "book_appointment" ? "REVIEW APPOINTMENT" : "REVIEW REQUEST"}
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
          This proposal has expired. Cancel it and start a new request.
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
