import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../models/api.js";
import { localDate, addDays } from "../../models/dates.js";
import { formatWhen } from "../../models/reminders.js";
import ReminderBanner from "./ReminderBanner.jsx";

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
}) {
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
      </div>
      {tab === "appointments" && (
        <Appointments
          api={api}
          timeZone={timeZone}
          disabled={disabled}
          onPropose={conversation.proposeAppointment}
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
    </section>
  );
}

function Appointments({ api, timeZone, disabled, onPropose, revision }) {
  const [providers, setProviders] = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [providerId, setProviderId] = useState("");
  const [from, setFrom] = useState(() => localDate(timeZone));
  const [to, setTo] = useState(() => addDays(localDate(timeZone), 7));
  const [slots, setSlots] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  const search = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setSlots(null);
    Promise.all([
      api.listProviders(controller.signal),
      api.listAppointments(controller.signal),
    ])
      .then(([doctors, visits]) => {
        if (controller.signal.aborted) return;
        setProviders(doctors);
        setAppointments(visits);
        setProviderId((id) =>
          doctors.some((doctor) => doctor.id === id)
            ? id
            : doctors[0]?.id || "",
        );
      })
      .catch((error) => {
        if (!controller.signal.aborted) setError(errorMessage(error));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => {
      controller.abort();
      search.current?.abort();
    };
  }, [api, revision, reload]);
  function clearSlots() {
    search.current?.abort();
    setSearching(false);
    setSlots(null);
  }
  async function find(event) {
    event.preventDefault();
    search.current?.abort();
    const controller = new AbortController();
    search.current = controller;
    setSlots(null);
    setError("");
    if (!from || !to || to < from || to > addDays(from, 31)) {
      setError("Choose an end date within 31 days of the start date.");
      return;
    }
    setSearching(true);
    try {
      const result = await api.listSlots(
        providerId,
        from,
        to,
        controller.signal,
      );
      if (!controller.signal.aborted) setSlots(result);
    } catch (error) {
      if (!controller.signal.aborted) setError(errorMessage(error));
    } finally {
      if (!controller.signal.aborted) setSearching(false);
    }
  }
  return (
    <div className="care-content">
      <h3>Choose an appointment</h3>
      <p>
        Choose a time, then review and confirm it in the conversation. Selecting
        a time does not book it.
      </p>
      <p className="quiet-label">Times shown in {timeZone}.</p>
      {loading && <p role="status">Loading appointments...</p>}
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <button
        className="secondary"
        disabled={loading || disabled}
        onClick={() => setReload((n) => n + 1)}
      >
        Refresh appointments
      </button>
      <form className="care-form" onSubmit={find}>
        <label>
          Doctor
          <select
            value={providerId}
            disabled={loading || disabled}
            onChange={(event) => {
              clearSlots();
              setProviderId(event.target.value);
            }}
          >
            {!providers.length && (
              <option value="">No doctors available</option>
            )}
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name} — {provider.specialty}
              </option>
            ))}
          </select>
        </label>
        <label>
          From date
          <input
            type="date"
            value={from}
            required
            disabled={disabled}
            onChange={(event) => {
              clearSlots();
              setFrom(event.target.value);
            }}
          />
        </label>
        <label>
          Through date
          <input
            type="date"
            value={to}
            required
            disabled={disabled}
            onChange={(event) => {
              clearSlots();
              setTo(event.target.value);
            }}
          />
        </label>
        <button
          className="primary"
          disabled={loading || searching || disabled || !providerId}
        >
          Find times
        </button>
      </form>
      {searching && <p role="status">Finding available times...</p>}
      {slots?.length === 0 && (
        <p role="status">
          No available times. Try another doctor or date range.
        </p>
      )}
      <ul className="care-list">
        {slots?.map((slot) => (
          <li key={slot.slot_id}>
            <strong>{slot.provider.name}</strong>
            <p>{formatWhen(slot.starts_at, timeZone)}</p>
            <button
              className="secondary"
              disabled={disabled}
              onClick={async () => {
                if (await onPropose(slot)) setSlots(null);
              }}
            >
              Review this time
            </button>
          </li>
        ))}
      </ul>
      <h3>Upcoming appointments</h3>
      {!loading && !error && !appointments.length && (
        <p>No upcoming appointments.</p>
      )}
      <ul className="care-list">
        {appointments.map((visit) => (
          <li key={visit.id}>
            <strong>{visit.provider.name}</strong>
            <p>{formatWhen(visit.starts_at, timeZone)}</p>
            <p>
              {visit.location} · {visit.status}
            </p>
          </li>
        ))}
      </ul>
    </div>
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
