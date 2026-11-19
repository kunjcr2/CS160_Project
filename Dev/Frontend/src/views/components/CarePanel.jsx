import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../models/api.js";
import { localDate } from "../../models/dates.js";
import ReminderBanner from "./ReminderBanner.jsx";
import MessageDoctor from "./MessageDoctor.jsx";
import { HelpRequest, RefillRequests } from "./CareRequests.jsx";
import SupportQueue from "./SupportQueue.jsx";
import Appointments from "./Appointments.jsx";

export default function CarePanel({
  api,
  user,
  timeZone,
  disabled,
  conversation,
  onReminderChange,
  tab,
  setTab,
  panelRef,
  careIntent,
}) {
  const [messageDraft, setMessageDraft] = useState({ providerId: "", body: "" });
  const messageAttempt = useRef(null);
  const [helpDraft, setHelpDraft] = useState("");
  const helpAttempt = useRef(null);
  const [helpReceipt, setHelpReceipt] = useState(null);
  const [helpReason, setHelpReason] = useState("user_request");
  const canMessage = !user || user.role === "older_adult";
  useEffect(() => {
    const outcome = conversation.lastResolution;
    if (outcome?.status === "executed" && ["book_appointment", "cancel_appointment", "reschedule_appointment"].includes(outcome.actionType))
      onReminderChange();
  }, [conversation.lastResolution, onReminderChange]);
  useEffect(() => {
    if (careIntent?.kind !== "human_help") return;
    setHelpReason(careIntent.reason === "repeated_failures" ? "repeated_failures" : "user_request");
    if (typeof careIntent.summary === "string") setHelpDraft((value) => value || careIntent.summary.slice(0, 300));
  }, [careIntent]);
  useEffect(() => {
    const outcome = conversation.lastResolution;
    if (outcome?.actionType === "request_help" && outcome.status === "executed") setHelpReceipt(outcome);
    const attempt = helpAttempt.current;
    if (!outcome || !attempt || outcome.id !== attempt.id) return;
    if (outcome.status === "executed") setHelpDraft((value) => value.trim() === attempt.summary ? "" : value);
    helpAttempt.current = null;
  }, [conversation.lastResolution]);
  useEffect(() => {
    const outcome = conversation.lastResolution;
    const attempt = messageAttempt.current;
    if (!outcome || !attempt || outcome.id !== attempt.id) return;
    if (outcome.status === "executed") {
      setMessageDraft((draft) => draft.body === attempt.body && draft.providerId === attempt.providerId
        ? { ...draft, body: "" } : draft);
    }
    messageAttempt.current = null;
  }, [conversation.lastResolution]);

  async function proposeMessage(providerId, body) {
    const action = await conversation.proposeCareMessage(user?.id || "demo", providerId, body);
    if (action) messageAttempt.current = { id: action.id, providerId, body };
    return action;
  }

  return (
    <section
      ref={panelRef}
      tabIndex={-1}
      className="care-panel"
      aria-label="My care"
    >
      <h2>My care</h2>
      <div className="button-row">
        <button
          className="secondary"
          aria-expanded={tab === "appointments"}
          onClick={() => setTab(tab === "appointments" ? "" : "appointments")}
        >
          Find appointments
        </button>
        {(!user || user.role === "older_adult") && (
          <button
            className="secondary"
            aria-expanded={tab === "medications"}
            onClick={() => setTab(tab === "medications" ? "" : "medications")}
          >
            My medications
          </button>
        )}
        {canMessage && <button className="secondary" aria-expanded={tab === "messages"}
          onClick={() => setTab(tab === "messages" ? "" : "messages")}>Message my doctor</button>}
        {canMessage && <>
          <button className="secondary" aria-expanded={tab === "refills"}
            onClick={() => setTab(tab === "refills" ? "" : "refills")}>Prescription refills</button>
          <button className="secondary" aria-expanded={tab === "help"}
            onClick={() => { setHelpReason("user_request"); setTab(tab === "help" ? "" : "help"); }}>Help</button>
        </>}
        {api.mode === "demo" && <button className="secondary" aria-expanded={tab === "support"}
          onClick={() => setTab(tab === "support" ? "" : "support")}>Preview support queue</button>}
      </div>
      {tab === "appointments" && (
        <Appointments
          api={api}
          timeZone={timeZone}
          disabled={disabled}
          onPropose={conversation.proposeAppointment}
          onCancel={conversation.proposeCancellation}
          onReschedule={conversation.proposeReschedule}
          revision={conversation.careRevision}
        />
      )}
      {tab === "medications" && (
        <Medications
          api={api}
          userId={user?.id || "demo"}
          timeZone={timeZone}
          onReminderChange={onReminderChange}
        />
      )}
      {tab === "messages" && canMessage && <MessageDoctor api={api} olderAdultId={user?.id || "demo"}
        timeZone={timeZone} disabled={disabled} draft={messageDraft} setDraft={setMessageDraft}
        onPropose={proposeMessage} revision={conversation.careRevision} proposalError={conversation.error} />}
      {tab === "help" && canMessage && <HelpRequest api={api} userId={user?.id || "demo"}
        timeZone={timeZone} disabled={disabled} draft={helpDraft} setDraft={setHelpDraft}
        revision={conversation.careRevision} proposalError={conversation.error}
        receipt={helpReceipt}
        onPropose={async (summary) => {
          const action = await conversation.proposeHumanHelp(user?.id || "demo", summary, helpReason);
          if (action) helpAttempt.current = { id: action.id, summary };
        }} />}
      {tab === "refills" && canMessage && <RefillRequests api={api} userId={user?.id || "demo"}
        timeZone={timeZone} disabled={disabled} revision={conversation.careRevision}
        proposalError={conversation.error} onPropose={(id) => conversation.proposeRefill(user?.id || "demo", id)}
        onMessageDoctor={(medication) => {
          setMessageDraft((value) => value.body.trim() ? value : {
            ...value, body: medication ? `I have a question about refilling ${medication.name}, ${medication.dosage}. Could you help me with the next step?` : "",
          });
          setTab("messages");
        }} />}
      {tab === "support" && api.mode === "demo" && <SupportQueue api={api} timeZone={timeZone} />}
    </section>
  );
}

function Medications({ api, userId, timeZone, onReminderChange }) {
  const [date, setDate] = useState(() => localDate(timeZone));
  const [medications, setMedications] = useState([]);
  const [doses, setDoses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const [blocked, setBlocked] = useState(false);
  const generation = useRef(0);
  const active = useRef(false);
  const locked = useRef(false);
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    const refresh = async () => {
      if (locked.current) return;
      const version = ++generation.current;
      setLoading(true);
      try {
        const [meds, reminders] = await Promise.all([
          api.listMedications(userId, controller.signal),
          api.listMedicationReminders(userId, date, controller.signal),
        ]);
        if (controller.signal.aborted || version !== generation.current) return;
        setMedications(meds);
        setDoses(reminders);
        setBlocked(false);
        setError("");
      } catch (error) {
        if (!controller.signal.aborted && version === generation.current) {
          setError(errorMessage(error));
          setBlocked(true);
        }
      } finally {
        if (!controller.signal.aborted && version === generation.current)
          setLoading(false);
      }
    };
    setDoses([]);
    setBlocked(true);
    refresh();
    const unsubscribe = api.subscribe(refresh, () => {});
    window.addEventListener("focus", refresh);
    return () => {
      active.current = false;
      ++generation.current;
      controller.abort();
      unsubscribe();
      window.removeEventListener("focus", refresh);
    };
  }, [api, userId, date, reload]);
  async function answer(dose, status) {
    if (locked.current || blocked) return;
    locked.current = true;
    ++generation.current;
    setBusy(true);
    setLoading(false);
    setError("");
    try {
      const updated = await api.answerReminder(dose, status);
      if (!active.current) return;
      setDoses((rows) =>
        rows.map((row) => (row.id === updated.id ? updated : row)),
      );
      onReminderChange();
    } catch (error) {
      if (active.current) {
        setError(errorMessage(error));
        setBlocked(true);
      }
    } finally {
      locked.current = false;
      if (active.current) {
        setBusy(false);
      }
    }
  }
  return (
    <div className="care-content">
      <h3>Medications and doses</h3>
      <p className="quiet-label">Your medication schedule uses {timeZone}.</p>
      <ul className="care-list">
        {medications.map((med) => (
          <li key={med.id}>
            <strong>
              {med.name} · {med.dosage}
            </strong>
            {med.instructions && <p>{med.instructions}</p>}
            <p>{med.stopped_at ? "Stopped" : "Scheduled"}</p>
            {med.schedules.map((schedule, index) => (
              <p key={index}>
                {schedule.time_of_day.slice(0, 5)} ·{" "}
                {schedule.days_of_week.length === 7
                  ? "Every day"
                  : schedule.days_of_week
                      .map(
                        (day) =>
                          ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][
                            day
                          ],
                      )
                      .join(", ")}
              </p>
            ))}
          </li>
        ))}
      </ul>
      <label className="care-form">
        Dose date
        <input
          type="date"
          value={date}
          required
          disabled={busy}
          onChange={(event) => {
            if (event.target.value) setDate(event.target.value);
          }}
        />
      </label>
      <button
        className="secondary"
        disabled={loading || busy}
        onClick={() => setReload((n) => n + 1)}
      >
        Refresh doses
      </button>
      {loading && <p role="status">Updating doses...</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!loading && !error && !doses.length && <p>No doses for this date.</p>}
      <div
        className="reminder-list"
        aria-label="Daily doses"
        aria-live="polite"
      >
        {doses.map((dose) => (
          <ReminderBanner
            key={dose.id}
            reminder={dose}
            timeZone={timeZone}
            busy={busy}
            disabled={busy || loading || blocked}
            onAnswer={answer}
          />
        ))}
      </div>
    </div>
  );
}
