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
  Mic,
  Square,
  Volume2,
  LogOut,
} from "lucide-react";
import { createApi, errorMessage } from "./models/api.js";
import { createDemoApi } from "./models/demo.js";
import { reminderKey } from "./models/reminders.js";
import { useConversation } from "./controllers/useConversation.js";
import { useNotifications } from "./controllers/useNotifications.js";
import ConfirmationCard from "./views/components/ConfirmationCard.jsx";
import ReminderBanner from "./views/components/ReminderBanner.jsx";
import SignIn from "./views/components/SignIn.jsx";
import { useVoice, useSpeechPlayback } from "./controllers/useVoice.js";

const mode =
  import.meta.env.VITE_DATA_MODE || (import.meta.env.DEV ? "demo" : "live");
export default function App() {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(mode === "demo");
  const [sessionError, setSessionError] = useState("");
  const [api] = useState(() =>
    mode === "demo"
      ? createDemoApi()
      : createApi({
          notificationsPath:
            import.meta.env.VITE_NOTIFICATIONS_PATH || "/api/v1/notifications",
          onUnauthorized: () => {
            setUser(null);
            setSessionError("Your session has expired. Please sign in again.");
          },
        }),
  );
  useEffect(() => {
    if (api.mode === "demo") return;
    let active = true;
    api
      .restoreSession()
      .then((value) => {
        if (active) setUser(value);
      })
      .catch((error) => {
        if (active && error.status !== 401)
          setSessionError(errorMessage(error));
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [api]);
  if (!ready)
    return (
      <main className="sign-in">
        <h1>Care Companion</h1>
        <p role="status">Checking your session...</p>
      </main>
    );
  if (api.mode !== "demo" && !user)
    return (
      <SignIn
        api={api}
        initialError={sessionError}
        onSignIn={(value) => {
          setUser(value);
          setSessionError("");
        }}
      />
    );
  return (
    <Companion
      key={user?.id || "demo"}
      api={api}
      user={user}
      onSignOut={() => setUser(null)}
    />
  );
}

function Companion({ api, user, onSignOut }) {
  const conversation = useConversation(api);
  const notifications = useNotifications(api);
  const [draft, setDraft] = useState("");
  const [largeText, setLargeText] = useState(false);
  const [demoNotice, setDemoNotice] = useState("");
  const end = useRef(null);
  const input = useRef(null);
  const initialScroll = useRef(true);
  const [autoSpeak, setAutoSpeak] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [accountError, setAccountError] = useState("");
  const speech = useSpeechPlayback(api);
  const voice = useVoice(api, (text) => {
    setDraft((value) => (value.trim() ? `${value.trim()}\n${text}` : text));
    input.current?.focus();
  });
  const lastReply = useRef("welcome");
  const voiceBusy = voice.state !== "idle";
  const timeZone =
    user?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
  const sent = notifications.reminders.filter(
    (item) => item.status === "sent",
  ).length;
  const occupied = Boolean(
    conversation.busy || conversation.proposal || voiceBusy || signingOut,
  );

  useEffect(() => {
    const reply = conversation.messages.at(-1);
    if (reply.role !== "assistant" || reply.id === lastReply.current) return;
    lastReply.current = reply.id;
    if (autoSpeak && api.mode === "live")
      speech.play(
        [reply.text, reply.notice].filter(Boolean).join(" "),
        reply.id,
      );
  }, [conversation.messages, autoSpeak, api]);

  async function signOut() {
    setSigningOut(true);
    setAccountError("");
    voice.cancel();
    speech.stop();
    try {
      await api.signOut();
      onSignOut();
    } catch (error) {
      setAccountError(errorMessage(error));
    } finally {
      setSigningOut(false);
    }
  }

  useEffect(() => {
    if (initialScroll.current) {
      initialScroll.current = false;
      return;
    }
    end.current?.scrollIntoView({ block: "nearest", behavior: "instant" });
  }, [conversation.messages, conversation.busy]);

  function submit(event) {
    event.preventDefault();
    if (!draft.trim() || draft.length > 2000 || occupied) return;
    speech.stop();
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
        <div className="header-actions">
          {user && (
            <span className="quiet-label">
              {user.preferred_name || user.display_name}
            </span>
          )}
          <button
            className="secondary text-toggle"
            type="button"
            aria-pressed={largeText}
            onClick={() => setLargeText(!largeText)}
          >
            <Type size={20} aria-hidden="true" />
            Larger text
          </button>
          {user && (
            <button
              className="icon-button"
              title="Sign out"
              aria-label="Sign out"
              disabled={
                signingOut ||
                Boolean(conversation.busy) ||
                Boolean(notifications.busy)
              }
              onClick={signOut}
            >
              <LogOut size={20} aria-hidden="true" />
            </button>
          )}
        </div>
      </header>
      {accountError && (
        <p className="error" role="alert">
          {accountError}
        </p>
      )}
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
                {message.notice && (
                  <p className="proposal-notice" role="status">
                    {message.notice}
                  </p>
                )}
                {message.role === "assistant" && message.id !== "welcome" && (
                  <div className="reply-audio">
                    <button
                      className="icon-button"
                      type="button"
                      title={
                        api.mode === "demo"
                          ? "Voice playback requires live mode"
                          : speech.id === message.id &&
                              ["loading", "playing"].includes(speech.state)
                            ? "Stop reply"
                            : "Play reply"
                      }
                      aria-label={
                        speech.id === message.id &&
                        ["loading", "playing"].includes(speech.state)
                          ? "Stop reply"
                          : "Play reply"
                      }
                      disabled={api.mode === "demo" || voiceBusy || signingOut}
                      onClick={() =>
                        speech.id === message.id &&
                        ["loading", "playing"].includes(speech.state)
                          ? speech.stop()
                          : speech.play(
                              [message.text, message.notice]
                                .filter(Boolean)
                                .join(" "),
                              message.id,
                            )
                      }
                    >
                      {speech.id === message.id &&
                      ["loading", "playing"].includes(speech.state) ? (
                        <Square size={20} aria-hidden="true" />
                      ) : (
                        <Volume2 size={20} aria-hidden="true" />
                      )}
                    </button>
                    {speech.id === message.id && speech.state === "loading" && (
                      <span role="status">Preparing audio...</span>
                    )}
                    {speech.id === message.id && speech.state === "playing" && (
                      <span role="status">Responding...</span>
                    )}
                    {speech.id === message.id && speech.error && (
                      <span role="alert">{speech.error}</span>
                    )}
                  </div>
                )}
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
                disabled={!draft.trim() || draft.length > 2000 || occupied}
              >
                <Send size={22} aria-hidden="true" />
                <span>Send</span>
              </button>
            </div>
            {draft.length > 2000 && (
              <p className="error" role="alert">
                Your message is too long. Please shorten it to 2,000 characters
                before sending.
              </p>
            )}
          </form>
          <div className="voice-toolbar" aria-label="Voice controls">
            {voice.state === "recording" ? (
              <button className="primary" onClick={voice.stop}>
                <Square size={20} aria-hidden="true" />
                Stop recording
              </button>
            ) : (
              <button
                className="icon-button"
                aria-label="Record message"
                title={
                  api.mode === "demo"
                    ? "Recording requires live mode"
                    : !voice.supported
                      ? "Recording unavailable in this browser"
                      : "Record message"
                }
                disabled={occupied || api.mode === "demo" || !voice.supported}
                onClick={() => {
                  speech.stop();
                  voice.start();
                }}
              >
                <Mic size={22} aria-hidden="true" />
              </button>
            )}
            {voiceBusy && (
              <button
                className="icon-button"
                aria-label="Cancel recording"
                title="Cancel recording"
                onClick={voice.cancel}
              >
                <X size={20} aria-hidden="true" />
              </button>
            )}
            <span className="voice-status" role="status">
              {voice.state === "recording"
                ? `Recording ${voice.seconds}s / 60s`
                : voice.state === "transcribing"
                  ? "Transcribing..."
                  : voice.state === "permission"
                    ? "Waiting for microphone permission..."
                    : ""}
            </span>
            <label className="speech-toggle">
              <input
                type="checkbox"
                checked={autoSpeak}
                disabled={api.mode === "demo"}
                onChange={(event) => {
                  setAutoSpeak(event.target.checked);
                  if (!event.target.checked) speech.stop();
                }}
              />
              Read replies aloud
            </label>
          </div>
          {voice.error && (
            <p className="error" role="alert">
              {voice.error}
            </p>
          )}
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
                timeZone={timeZone}
                canAnswerMedication={
                  api.mode === "demo" || user?.role === "older_adult"
                }
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
          {api.mode !== "demo" && (
            <p className="delivery-status" role="status">
              {notifications.error
                ? "Reminder updates unavailable."
                : "Checking for reminders every 20 seconds."}
            </p>
          )}
          <p className="timezone-note">
            Times shown in {timeZone.replaceAll("_", " ")}.
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
