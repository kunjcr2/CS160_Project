import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../models/api.js";
import { localDate, addDays } from "../../models/dates.js";
import { formatWhen } from "../../models/reminders.js";

export default function Appointments({ api, timeZone, disabled, onPropose, onCancel, onReschedule, revision }) {
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
  const [rescheduling, setRescheduling] = useState(null);
  const form = useRef(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    setSlots(null);
    setRescheduling(null);
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
        if (!controller.signal.aborted) {
          setError(errorMessage(error)); setAppointments([]); setProviders([]);
        }
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
      <h3>{rescheduling ? "Choose a new time" : "Choose an appointment"}</h3>
      <p>
        Choose a time, then review and confirm it in the conversation. Selecting
        a time does not book it.
      </p>
      <p className="quiet-label">Times shown in {timeZone}.</p>
      {rescheduling && <div className="service-notice" role="status">
        <p>Moving your appointment with {rescheduling.provider.name} from {formatWhen(rescheduling.starts_at, timeZone)}. Choose a new time with the same doctor.</p>
        <button className="secondary" disabled={disabled} onClick={() => { clearSlots(); setRescheduling(null); }}>Exit rescheduling</button>
      </div>}
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
      <form ref={form} tabIndex={-1} className="care-form" onSubmit={find}>
        <label>
          Doctor
          <select
            value={providerId}
            disabled={loading || disabled || Boolean(rescheduling)}
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
                if (rescheduling && slot.provider.id !== rescheduling.provider.id) {
                  setError("Choose a time with the same doctor."); return;
                }
                if (await (rescheduling ? onReschedule(rescheduling.id, slot.slot_id) : onPropose(slot))) setSlots(null);
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
            {visit.status === "booked" && Date.parse(visit.starts_at) > Date.now() && <div className="button-row">
              <button className="secondary" disabled={disabled || loading} onClick={() => onCancel(visit.id)}>Cancel appointment</button>
              <button className="secondary" disabled={disabled || loading} onClick={() => {
                clearSlots(); setRescheduling(visit); setProviderId(visit.provider.id);
                form.current?.focus(); form.current?.scrollIntoView({ block: "center" });
              }}>Reschedule appointment</button>
            </div>}
          </li>
        ))}
      </ul>
    </div>
  );
}
