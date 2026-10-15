import { useEffect, useRef, useState } from "react";
import {
  Send,
  RotateCcw,
  Bell,
  MessageCircle,
  FlaskConical,
  Check,
  X,
  Pill,
  CalendarDays,
  RefreshCw,
  Type,
  CircleAlert,
} from "lucide-react";
import { createApi } from "./models/api.js";
import { createDemoApi } from "./models/demo.js";
import { reminderKey } from "./models/reminders.js";
import { useConversation } from "./controllers/useConversation.js";
import { useNotifications } from "./controllers/useNotifications.js";
import ConfirmationCard from "./views/components/ConfirmationCard.jsx";
import ReminderBanner from "./views/components/ReminderBanner.jsx";

const mode =
  import.meta.env.VITE_DATA_MODE || (import.meta.env.DEV ? "demo" : "live");
const api =
  mode === "demo"
    ? createDemoApi()
    : createApi({
        notificationsPath:
          import.meta.env.VITE_NOTIFICATIONS_PATH || "/notifications",
        streamPath: import.meta.env.VITE_NOTIFICATION_STREAM_PATH || "",
      });

export default function App() {
  const conversation = useConversation(api);
  const notifications = useNotifications(api);
  const [draft, setDraft] = useState("");
  const [largeText, setLargeText] = useState(false);
  const [demoNotice, setDemoNotice] = useState("");
  const end = useRef(null);
  const input = useRef(null);
  const initialScroll = useRef(true);
  const sent = notifications.reminders.filter(
    (item) => item.status === "sent",
  ).length;
  const occupied = Boolean(conversation.busy || conversation.proposal);

  useEffect(() => {
    if (initialScroll.current) {
      initialScroll.current = false;
      return;
    }
    end.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [conversation.messages, conversation.busy]);

  function submit(event) {
    event.preventDefault();
    if (!draft.trim() || occupied) return;
    conversation.send(draft);
    setDraft("");
    input.current?.focus();
  }

  return (
    <div className={`app-shell${largeText ? " large-text" : ""}`}>
      <a className="skip-link" href="#message-input">
        Skip to message
      </a>
      {api.mode === "demo" && (
        <div className="demo-banner">
          <FlaskConical size={18} aria-hidden="true" />
          <strong>Demo mode</strong>
          <span>Sample data only. Nothing is saved to your care record.</span>
        </div>
      )}
      <header className="app-header">
        <div className="brand">
          <div>
            <h1>Care Companion</h1>
            <p>Appointments &amp; reminders</p>
          </div>
        </div>
        <button
          className="secondary text-toggle"
          type="button"
          aria-pressed={largeText}
          onClick={() => setLargeText(!largeText)}
        >
          <Type size={20} aria-hidden="true" />
          Larger text
        </button>
      </header>
      <main className="workspace">
        <section
          className="conversation-panel"
          aria-labelledby="conversation-title"
        >
          <div className="section-heading">
            <div>
              <p className="eyebrow">YOUR COMPANION</p>
              <h2 id="conversation-title">
                <MessageCircle size={25} aria-hidden="true" />
                Let's talk
              </h2>
            </div>
            <span className="quiet-label">
              {api.mode === "demo" ? "Sample conversation" : "Conversation"}
            </span>
          </div>
          <div
            className="messages"
            role="log"
            aria-label="Conversation messages"
            aria-relevant="additions text"
            aria-live="polite"
          >
            {conversation.messages.map((message) => (
              <article
                key={message.id}
                className={`message message--${message.role}`}
              >
                <span className="speaker">
                  {message.role === "user" ? "You" : "Companion"}
                </span>
                <p>{message.text}</p>
              </article>
            ))}
            {conversation.busy === "thinking" && (
              <p className="thinking" role="status">
                Thinking<span aria-hidden="true">...</span>
              </p>
            )}
            <div ref={end} />
          </div>
          {conversation.proposal && (
            <ConfirmationCard
              proposal={conversation.proposal}
              busy={conversation.busy}
              onResolve={conversation.resolve}
            />
          )}
          {conversation.error && (
            <div className="error" role="alert">
              <CircleAlert size={22} aria-hidden="true" />
              <div>
                <p>{conversation.error}</p>
                {conversation.failedText && (
                  <button
                    className="secondary"
                    disabled={Boolean(conversation.busy)}
                    onClick={() =>
                      conversation.send(conversation.failedText, true)
                    }
                  >
                    <RotateCcw size={18} aria-hidden="true" />
                    Retry message
                  </button>
                )}
              </div>
            </div>
          )}
          {!conversation.proposal && (
            <div className="quick-prompts" aria-label="Conversation starters">
              <button
                className="secondary"
                disabled={occupied}
                onClick={() => {
                  setDraft("I'd like to book a doctor appointment.");
                  input.current?.focus();
                }}
              >
                <CalendarDays size={20} aria-hidden="true" />
                Book an appointment
              </button>
              <button
                className="secondary"
                disabled={occupied}
                onClick={() => {
                  setDraft("Show my reminders.");
                  input.current?.focus();
                }}
              >
                <Bell size={20} aria-hidden="true" />
                My reminders
              </button>
            </div>
          )}
          <form className="composer" onSubmit={submit}>
            <label htmlFor="message-input">Your message</label>
            <div>
              <textarea
                ref={input}
                id="message-input"
                rows={2}
                maxLength={2000}
                value={draft}
                disabled={occupied}
                onChange={(event) => setDraft(event.target.value)}
                placeholder={
                  conversation.proposal
                    ? "Review the appointment above first"
                    : "What would you like help with?"
                }
              />
              <button
                className="primary send-button"
                type="submit"
                disabled={!draft.trim() || occupied}
              >
                <Send size={22} aria-hidden="true" />
                <span>Send</span>
              </button>
            </div>
          </form>
        </section>
        <aside className="today-panel" aria-labelledby="today-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">YOUR REMINDERS</p>
              <h2 id="today-title">
                <Bell size={25} aria-hidden="true" />
                Today
              </h2>
            </div>
            <button
              type="button"
              className="icon-button"
              title="Refresh reminders"
              aria-label="Refresh reminders"
              disabled={notifications.loading || Boolean(notifications.busy)}
              onClick={notifications.refresh}
            >
              <RefreshCw size={22} aria-hidden="true" />
            </button>
          </div>
          <p className="reminder-count">
            {sent
              ? `${sent} reminder${sent === 1 ? "" : "s"} waiting for you`
              : "No reminders waiting for a response"}
          </p>
          {notifications.loading && (
            <p className="quiet-label" role="status">
              Updating reminders...
            </p>
          )}
          {notifications.error && (
            <div className="error" role="alert">
              <CircleAlert size={22} aria-hidden="true" />
              <div>
                <p>{notifications.error}</p>
                <button
                  className="secondary"
                  disabled={
                    notifications.loading || Boolean(notifications.busy)
                  }
                  onClick={notifications.refresh}
                >
                  <RotateCcw size={18} aria-hidden="true" />
                  Retry reminders
                </button>
              </div>
            </div>
          )}
          <div
            className="reminder-list"
            aria-live="polite"
            aria-relevant="additions text"
          >
            {notifications.reminders.map((reminder) => (
              <ReminderBanner
                key={reminderKey(reminder)}
                reminder={reminder}
                busy={notifications.busy === reminderKey(reminder)}
                disabled={
                  Boolean(notifications.busy) ||
                  notifications.blocked.includes(reminderKey(reminder))
                }
                onAnswer={notifications.answer}
              />
            ))}
            {!notifications.loading &&
              !notifications.error &&
              !notifications.reminders.length && (
                <div className="empty-state">
                  <Check size={28} aria-hidden="true" />
                  <p>You're all caught up.</p>
                </div>
              )}
          </div>
          <span className="sr-only" role="status">
            {notifications.announcement}
          </span>
          {api.mode !== "demo" && notifications.delivery !== "connected" && (
            <p className="delivery-status" role="status">
              {notifications.delivery === "manual"
                ? "Refresh to check for new reminders."
                : "Live updates are reconnecting. You can still refresh reminders."}
            </p>
          )}
          <p className="timezone-note">
            Times shown in{" "}
            {Intl.DateTimeFormat()
              .resolvedOptions()
              .timeZone.replaceAll("_", " ")}
            .
          </p>
        </aside>
      </main>
      {api.mode === "demo" && (
        <details className="demo-tools">
          <summary>Demo controls</summary>
          <div className="demo-controls">
            <button
              className="secondary"
              disabled={Boolean(notifications.busy)}
              onClick={() => {
                api.simulateMissed();
                setDemoNotice("Simulated a missed-dose update.");
              }}
            >
              <Pill size={18} aria-hidden="true" />
              Simulate automatic missed
            </button>
            <button
              className="secondary"
              disabled={Boolean(notifications.busy)}
              onClick={() => {
                api.resetReminders();
                setDemoNotice("Sample reminders reset.");
              }}
            >
              <RefreshCw size={18} aria-hidden="true" />
              Reset reminders
            </button>
            <button
              className="secondary"
              onClick={() => {
                api.failNextRequest();
                setDemoNotice("The next demo request will fail once.");
              }}
            >
              <X size={18} aria-hidden="true" />
              Fail next request
            </button>
          </div>
          <p role="status">{demoNotice}</p>
        </details>
      )}
      <footer>
        CS 160 · Team 4
        <span>{api.mode === "demo" ? "Prototype" : "Care Companion"}</span>
      </footer>
    </div>
  );
}
