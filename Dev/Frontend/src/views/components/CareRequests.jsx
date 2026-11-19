import { useState } from "react";
import { useCareRecords } from "../../controllers/useCareRecords.js";
import { HELP_MAX_LENGTH, REQUEST_STATUS } from "../../models/careRequests.js";
import { formatWhen } from "../../models/reminders.js";

export function RequestAvailability({ api, enabled, service }) {
  if (!enabled) return <p className="service-notice" role="status">
    {service} is not available yet. Please try again later.
  </p>;
  if (api.mode === "demo") return <p className="service-notice">
    Demo only. Requests stay in this tab until you reload. No real person or pharmacy is contacted.
  </p>;
  return null;
}

export function RecordFeedback({ records, label }) {
  return <>
    {records.loading && <p role="status">Loading {label}...</p>}
    {records.error && <p className="error" role="alert">{records.error}</p>}
    <button className="secondary" disabled={records.loading} onClick={records.refresh}>
      Refresh {label}
    </button>
  </>;
}

function RequestHistory({ records, title, empty, timeZone, kind }) {
  return <section className="request-history" aria-label={title}>
    <h4>{title}</h4>
    <RecordFeedback records={records} label={kind === "help" ? "help requests" : "refill requests"} />
    {!records.loading && !records.error && !records.rows.length && <p>{empty}</p>}
    <ul className="care-list">
      {records.rows.map((row) => <li key={row.id}>
        <strong>{kind === "help" ? row.summary || "Help requested without a summary" : `${row.medication_name} · ${row.dosage}`}</strong>
        <p className="request-status">{REQUEST_STATUS[row.status] || "Status unavailable"}</p>
        {row.status_message && <p>{row.status_message}</p>}
        <p>{formatWhen(row.created_at, timeZone)}</p>
        {row.assigned_to && <p>Assigned to {row.assigned_to}</p>}
      </li>)}
    </ul>
  </section>;
}

export function HelpRequest({ api, userId, timeZone, disabled, draft, setDraft, onPropose, revision, proposalError, receipt }) {
  const enabled = api.careRequests?.help === true;
  const hasHistory = enabled && api.careRequests?.helpHistory === true;
  const records = useCareRecords(api, "listHelpRequests", userId, hasHistory, revision);
  return <div className="care-content">
    <h3>Ask for help</h3>
    <p>Share a short summary of what you need help with. Your conversation transcript is not included.</p>
    <RequestAvailability api={api} enabled={enabled} service="Human support" />
    <form className="care-form message-form" aria-label="Request support" onSubmit={(event) => {
      event.preventDefault();
      if (enabled && !disabled && draft.length <= HELP_MAX_LENGTH) onPropose(draft.trim());
    }}>
      <label htmlFor="help-summary">What do you need help with?</label>
      <textarea id="help-summary" rows={3} maxLength={HELP_MAX_LENGTH} value={draft}
        disabled={!enabled || disabled} onChange={(event) => setDraft(event.target.value)}
        aria-describedby="help-summary-hint" />
      <p id="help-summary-hint" className="quiet-label">Optional · {draft.length} / {HELP_MAX_LENGTH} characters. Review this summary before sharing it.</p>
      <button className="primary" disabled={!enabled || disabled || draft.length > HELP_MAX_LENGTH}>
        Review help request
      </button>
      {proposalError && <p className="error" role="alert">{proposalError}</p>}
    </form>
    {!hasHistory && api.mode === "live" && <section aria-label="Help submission">
      {receipt && <><h4>Help request submitted</h4><p role="status">{receipt.message}</p></>}
      <p>You can submit a request here. Live progress and previous help requests are not available on this screen.</p>
    </section>}
    {hasHistory && <RequestHistory records={records} title="Your help requests" kind="help"
      empty="No help requests yet." timeZone={timeZone} />}
  </div>;
}

export function RefillRequests({ api, userId, timeZone, disabled, onPropose, onMessageDoctor, revision, proposalError }) {
  const enabled = api.careRequests?.refills === true;
  // Reading existing medications uses the verified medication API even when
  // refill submission is unavailable. Never infer remaining refills from doses.
  const medications = useCareRecords(api, "listMedications", userId, true, revision);
  const history = useCareRecords(api, "listRefillRequests", userId, enabled, revision, { poll: api.mode === "live", paused: disabled });
  const [medicationId, setMedicationId] = useState("");
  const medication = medications.rows.find((row) => row.id === medicationId && !row.stopped_at);
  const known = Number.isInteger(medication?.refills_remaining) && medication.refills_remaining >= 0;
  const requested = history.rows.some((row) => row.medication_id === medicationId && ["submitted", "requested", "in_progress"].includes(row.status));
  const canSubmit = enabled && !disabled && medication && known && medication.refills_remaining > 0 &&
    !medications.loading && !medications.error && !history.loading && !history.error && !requested;
  return <div className="care-content">
    <h3>Prescription refills</h3>
    <p>Choose your prescribed medication, then review the request. Submitting a request does not mean a refill is approved or ready.</p>
    {api.mode === "live" && <p className="quiet-label">This prototype uses a simulated pharmacy. Status updates are checked every 20 seconds.</p>}
    <RequestAvailability api={api} enabled={enabled} service="Prescription refill service" />
    <RecordFeedback records={medications} label="medications" />
    {!medications.loading && !medications.error && !medications.rows.some((row) => !row.stopped_at) &&
      <p>No active medications are available. Contact your doctor about the prescription.</p>}
    <form className="care-form message-form" aria-label="Request a prescription refill" onSubmit={(event) => {
      event.preventDefault();
      if (canSubmit) onPropose(medication.id);
    }}>
      <label htmlFor="refill-medication">Medication to refill</label>
        <select id="refill-medication" value={medicationId} disabled={disabled || medications.loading || Boolean(medications.error)}
          onChange={(event) => setMedicationId(event.target.value)}>
          <option value="">Choose a medication</option>
          {medications.rows.filter((row) => !row.stopped_at).map((row) =>
            <option key={row.id} value={row.id}>{row.name} · {row.dosage}</option>)}
        </select>
      {medication && <div role="status">
        <p>{known ? `Refills remaining: ${medication.refills_remaining}` : "Remaining refills are unknown. Check with your doctor."}</p>
        {known && medication.refills_remaining === 0 && <p>No refills remain. Contact your doctor for the next step.</p>}
        {requested && <p>A request for this medication is already awaiting review.</p>}
      </div>}
      <button className="primary" disabled={!canSubmit}>Review refill request</button>
      {proposalError && <p className="error" role="alert">{proposalError}</p>}
    </form>
    <button className="secondary" onClick={() => onMessageDoctor(medication)}>Contact my doctor</button>
    {enabled && <RequestHistory records={history} title="Refill request history" kind="refill"
      empty="No refill requests yet." timeZone={timeZone} />}
  </div>;
}
