import { useEffect, useState } from "react";
import { errorMessage } from "../../models/api.js";
import { MESSAGE_MAX_LENGTH } from "../../models/careMessages.js";
import { formatWhen } from "../../models/reminders.js";

export default function MessageDoctor({ api, olderAdultId, timeZone, disabled,
  draft, setDraft, onPropose, revision, proposalError }) {
  const [providers, setProviders] = useState([]);
  const [providersLoading, setProvidersLoading] = useState(true);
  const [providerError, setProviderError] = useState("");
  const [providerReload, setProviderReload] = useState(0);
  const [messages, setMessages] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");
  const [historyReload, setHistoryReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setProvidersLoading(true); setProviderError("");
    api.listProviders(controller.signal).then((rows) => {
      if (!controller.signal.aborted) setProviders(rows);
    }).catch((error) => {
      if (!controller.signal.aborted) { setProviders([]); setProviderError(errorMessage(error)); }
    }).finally(() => { if (!controller.signal.aborted) setProvidersLoading(false); });
    return () => controller.abort();
  }, [api, providerReload]);

  useEffect(() => {
    const controller = new AbortController();
    setHistoryLoading(true); setHistoryError("");
    api.listCareMessages(olderAdultId, controller.signal).then((rows) => {
      if (!controller.signal.aborted) setMessages(rows);
    }).catch((error) => {
      if (!controller.signal.aborted) {
        // Do not retain possibly inaccessible data after consent/session changes.
        setMessages([]); setHistoryError(errorMessage(error));
      }
    }).finally(() => { if (!controller.signal.aborted) setHistoryLoading(false); });
    return () => controller.abort();
  }, [api, olderAdultId, revision, historyReload]);

  const validProvider = providers.some((provider) => provider.id === draft.providerId);
  const validBody = Boolean(draft.body.trim()) && draft.body.length <= MESSAGE_MAX_LENGTH;
  async function submit(event) {
    event.preventDefault();
    if (disabled || providersLoading || !validProvider || !validBody) return;
    await onPropose(draft.providerId, draft.body);
  }

  return <div className="care-content" aria-label="Doctor messages">
    <h3>Message my doctor</h3>
    <p>Choose a doctor and write a message. You will review it before confirming.</p>
    <p className="quiet-label">This prototype simulates delivery. No message reaches a real doctor.</p>
    {providersLoading && <p role="status">Loading doctors...</p>}
    {providerError && <div className="error" role="alert"><p>{providerError}</p>
      <button className="secondary" onClick={() => setProviderReload((n) => n + 1)}>Retry doctors</button></div>}
    {!providersLoading && !providerError && !providers.length && <p role="status">No doctors are available to message.</p>}
    <form className="care-form message-form" aria-label="Write to your doctor" onSubmit={submit}>
      <label htmlFor="message-doctor">Doctor to message</label>
      <select id="message-doctor" value={draft.providerId} required disabled={disabled || providersLoading}
        onChange={(event) => setDraft((value) => ({ ...value, providerId: event.target.value }))}>
        <option value="">Choose a doctor</option>
        {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name} — {provider.specialty}</option>)}
      </select>
      <label htmlFor="care-message-body">Message to your doctor</label>
      <textarea id="care-message-body" value={draft.body} rows={5} maxLength={MESSAGE_MAX_LENGTH}
        required disabled={disabled} aria-describedby="care-message-count"
        onChange={(event) => setDraft((value) => ({ ...value, body: event.target.value }))} />
      <p id="care-message-count" className="quiet-label">{draft.body.length} / {MESSAGE_MAX_LENGTH} characters</p>
      {proposalError && <p className="error" role="alert">{proposalError}</p>}
      <button className="primary" disabled={disabled || providersLoading || !validProvider || !validBody}>Review message</button>
    </form>
    <section className="message-history" aria-label="Message history">
      <div className="section-heading"><h3>Message history</h3>
        <button className="secondary" disabled={historyLoading} onClick={() => setHistoryReload((n) => n + 1)}>Refresh messages</button></div>
      {historyLoading && <p role="status">Loading messages...</p>}
      {historyError && <p className="error" role="alert">{historyError}</p>}
      {!historyLoading && !historyError && !messages.length && <p>No messages yet.</p>}
      <ul className="care-list" aria-live="polite">{messages.map((message) => <li key={message.id}>
        <article aria-label={`Message to ${message.provider.name}`}>
          <strong>{message.provider.name}</strong>
          <p className={message.status === "failed" ? "message-failed" : "quiet-label"}>{message.status === "sent" ? "Sent" : "Failed to send"}</p>
          <p className="care-message-text">{message.body}</p>
          <time dateTime={message.created_at}>{formatWhen(message.created_at, timeZone)}</time>
        </article>
      </li>)}</ul>
    </section>
  </div>;
}
