import { useEffect, useRef, useState } from "react";
import { errorMessage } from "../../models/api.js";
import { REQUEST_STATUS } from "../../models/careRequests.js";
import { useCareRecords } from "../../controllers/useCareRecords.js";
import { formatWhen } from "../../models/reminders.js";
import { RequestAvailability } from "./CareRequests.jsx";

export default function SupportQueue({ api, user, timeZone }) {
  const allowed = api.mode === "demo" || ["support_agent", "admin"].includes(user?.role);
  const enabled = allowed && api.careRequests?.queue === true;
  const waiting = api.mode === "demo" ? "waiting" : "open";
  const [filter, setFilter] = useState(waiting);
  const [selectedId, setSelectedId] = useState(null);
  const [busy, setBusy] = useState(false);
  const records = useCareRecords(api, "listSupportQueue", user?.id, enabled, 0,
    { poll: api.mode === "live", paused: busy });
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [blocked, setBlocked] = useState(false);
  const locked = useRef(false);
  const mounted = useRef(false);
  const detail = useRef(null);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { detail.current?.focus(); }, [selectedId]);
  const selected = records.rows.find((row) => row.id === selectedId);
  const visible = records.rows.filter((row) => filter === "all" || row.status === filter);

  function refresh() {
    setBlocked(false);
    setError("");
    records.refresh();
  }
  async function update(nextStatus) {
    if (!enabled || !selected || locked.current || records.loading || records.error || blocked) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const row = await api.updateSupportRequest(selected.id, selected.status, nextStatus);
      if (!mounted.current) return;
      setNotice(api.mode === "demo"
        ? `Sample request updated: ${REQUEST_STATUS[row.status]}. No real handoff occurred.`
        : `Request updated: ${REQUEST_STATUS[row.status]}.`);
      setSelectedId(null);
      records.refresh();
    } catch (error) {
      if (mounted.current) {
        setError(errorMessage(error));
        setBlocked(true);
      }
    } finally {
      locked.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  if (!allowed) return <p role="alert">This queue is available to support agents only.</p>;
  return <section className="care-content support-queue" aria-label="Support queue">
    <h3>{api.mode === "demo" ? "Demo support queue" : "Support queue"}</h3>
    <p>Review the shared summary, take a waiting request, and mark it resolved when finished.</p>
    <RequestAvailability api={api} enabled={enabled} service="The support queue" />
    {api.mode === "live" && <p className="quiet-label">Unresolved requests only, oldest first. Updates every 20 seconds. Resolved requests leave this queue.</p>}
    {enabled && <>
      <div className="care-form">
        <div className="queue-filter">
          <label htmlFor="queue-status">Queue status</label>
          <select id="queue-status" value={filter} disabled={busy} onChange={(event) => { setFilter(event.target.value); setSelectedId(null); }}>
            <option value={waiting}>Waiting for support</option>
            <option value="in_progress">In progress</option>
            {api.mode === "demo" && <option value="resolved">Resolved</option>}
            <option value="all">{api.mode === "demo" ? "All requests" : "All unresolved requests"}</option>
          </select>
        </div>
        <button className="secondary" disabled={busy || records.loading} onClick={refresh}>Refresh queue</button>
      </div>
      {records.loading && <p role="status">Loading support requests...</p>}
      {(records.error || error) && <p className="error" role="alert">{error || records.error}</p>}
      {notice && <p role="status">{notice}</p>}
      {!records.loading && !records.error && !visible.length && <p>No requests in this view.</p>}
      <div className="queue-layout">
        <ul className="care-list" aria-label="Queue requests">
          {visible.map((row) => <li key={row.id}>
            <strong>{row.display_name}</strong>
            <p>{REQUEST_STATUS[row.status] || "Status unavailable"}</p>
            <p>{formatWhen(row.created_at, timeZone)}</p>
            <button className="secondary" disabled={busy} aria-pressed={selectedId === row.id}
              onClick={() => { setSelectedId(row.id); setNotice(""); }}>
              View request from {row.display_name}
            </button>
          </li>)}
        </ul>
        {selected && <section ref={detail} tabIndex={-1} className="request-detail" aria-label="Request details">
          <h4>{selected.display_name}</h4>
          <p className="care-message-text">{selected.summary || "No summary was shared."}</p>
          <p>{REQUEST_STATUS[selected.status] || "Status unavailable"}</p>
          {selected.assigned_to && <p>Assigned to {selected.assigned_to}</p>}
          {selected.status === waiting && <button className="primary" disabled={busy || blocked}
            onClick={() => update("in_progress")}>{busy ? "Updating..." : "Take request"}</button>}
          {selected.status === "in_progress" && <button className="primary" disabled={busy || blocked}
            onClick={() => update("resolved")}>{busy ? "Updating..." : "Mark resolved"}</button>}
        </section>}
      </div>
    </>}
  </section>;
}

export function SupportWorkspace({ api, user, onSignOut }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [largeText, setLargeText] = useState(false);
  return <div className={`app-shell${largeText ? " large-text" : ""}`}>
    <header className="app-header">
      <div><h1>Care Companion</h1><p>Support workspace</p></div>
      <div className="header-actions">
        <span className="quiet-label">{user.display_name}</span>
        <button className="secondary" aria-pressed={largeText} onClick={() => setLargeText(!largeText)}>Larger text</button>
        <button className="secondary" disabled={busy} onClick={async () => {
          setBusy(true); setError("");
          try { await api.signOut(); onSignOut(); }
          catch (error) { setError(errorMessage(error)); }
          finally { setBusy(false); }
        }}>Sign out</button>
      </div>
    </header>
    {error && <p className="error" role="alert">{error}</p>}
    <main className="care-panel"><SupportQueue api={api} user={user}
      timeZone={user.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone} /></main>
  </div>;
}
