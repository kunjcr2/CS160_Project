import { useEffect, useState } from "react";
import { errorMessage } from "../../models/api.js";

export default function CaregiverWorkspace({ api, user, onSignOut }) {
  const [adults, setAdults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [code, setCode] = useState(null);
  const [loadError, setLoadError] = useState("");
  const [loadRevision, setLoadRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setLoadError("");
    api.listOlderAdults(controller.signal)
      .then(setAdults)
      .catch((failure) => {
        if (!controller.signal.aborted) setLoadError(errorMessage(failure));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api, loadRevision]);

  async function issueCode(adult) {
    setBusy(true);
    setError("");
    setCode(null);
    try {
      const result = await api.createPairingCode(adult.id);
      setCode({ ...result, name: adult.preferred_name || adult.display_name });
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  async function createAdult(event) {
    event.preventDefault();
    if (busy || loading || loadError) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    setBusy(true);
    setError("");
    setCode(null);
    try {
      const result = await api.createOlderAdult({
        display_name: values.get("displayName").trim(),
        preferred_name: values.get("preferredName").trim() || null,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "America/Los_Angeles",
        scopes: [],
      });
      setAdults((current) => [...current, result.older_adult]);
      form.reset();
      try {
        const pairing = await api.createPairingCode(result.older_adult.id);
        setCode({ ...pairing, name: result.older_adult.preferred_name || result.older_adult.display_name });
      } catch (failure) {
        setError(`Profile created, but the pairing code could not be created: ${errorMessage(failure)} Use Create pairing code beside the profile to try again.`);
      }
    } catch (failure) {
      setError(errorMessage(failure));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError("");
    try {
      await api.signOut();
      onSignOut();
    } catch (failure) {
      setError(errorMessage(failure));
      setBusy(false);
    }
  }

  return <main className="caregiver-workspace">
    <header className="caregiver-header">
      <div><p className="quiet-label">Care Companion</p><h1>Caregiver setup</h1></div>
      <button className="secondary" onClick={signOut} disabled={busy}>Sign out</button>
    </header>
    <p>Welcome, {user.display_name}. Create a profile for the person you support, then give them a one-time code to sign in on their device.</p>
    {error && <p className="error" role="alert">{error}</p>}
    {code && <section className="pairing-result" aria-live="polite">
      <h2>Pair {code.name}'s device</h2>
      <p>Open this app on their device, choose Pairing code, and enter:</p>
      <strong className="pairing-code">{code.code}</strong>
      <p>This code expires at {new Date(code.expires_at).toLocaleString()} and can be used once.</p>
    </section>}
    <section className="caregiver-section" aria-label="Older adult profiles">
      <h2>People you support</h2>
      {loading ? <p role="status">Loading profiles...</p> : loadError
        ? <div><p className="error" role="alert">Could not load profiles: {loadError}</p><button className="secondary" onClick={() => setLoadRevision((value) => value + 1)}>Retry loading profiles</button></div>
        : adults.length === 0
        ? <p>No profiles yet. Add one below to get started.</p>
        : <ul className="caregiver-list">{adults.map((adult) => <li key={adult.id}>
          <span>{adult.display_name}</span>
          <button className="secondary" disabled={busy} onClick={() => issueCode(adult)}>Create pairing code</button>
        </li>)}</ul>}
    </section>
    <section className="caregiver-section" aria-label="Add older adult">
      <h2>Add an older adult</h2>
      <form className="care-form" onSubmit={createAdult}>
        <label>Full name<input name="displayName" required maxLength={120} disabled={busy || loading || Boolean(loadError)} /></label>
        <label>Preferred name (optional)<input name="preferredName" maxLength={60} disabled={busy || loading || Boolean(loadError)} /></label>
        <button className="primary" disabled={busy || loading || Boolean(loadError)}>{busy ? "Please wait..." : "Create profile and pairing code"}</button>
      </form>
    </section>
  </main>;
}
