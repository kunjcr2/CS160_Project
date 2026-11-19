import { useState } from "react";
import { LogIn } from "lucide-react";
import { errorMessage } from "../../models/api.js";

export default function SignIn({ api, onSignIn, initialError }) {
  const [method, setMethod] = useState("pair");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      const values =
        method === "pair"
          ? { code: data.get("code").trim() }
          : { email: data.get("email").trim(), password: data.get("password") };
      onSignIn(await api.signIn(method, values));
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="sign-in">
      <h1>Care Companion</h1>
      <h2>Sign in</h2>
      <div className="sign-in-tabs" role="group" aria-label="Sign-in method">
        <button
          className="secondary"
          aria-pressed={method === "pair"}
          disabled={busy}
          onClick={() => {
            setMethod("pair");
            setError("");
          }}
        >
          Pairing code
        </button>
        <button
          className="secondary"
          aria-pressed={method === "login"}
          disabled={busy}
          onClick={() => {
            setMethod("login");
            setError("");
          }}
        >
          Email
        </button>
      </div>
      <form onSubmit={submit} key={method}>
        {method === "pair" ? (
          <label>
            Pairing code
            <input
              name="code"
              autoComplete="one-time-code"
              inputMode="numeric"
              pattern="[0-9]{8}"
              minLength={8}
              maxLength={8}
              required
              disabled={busy}
            />
          </label>
        ) : (
          <>
            <label>
              Email
              <input
                name="email"
                type="email"
                autoComplete="username"
                required
                disabled={busy}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                disabled={busy}
              />
            </label>
          </>
        )}
        {(error || initialError) && (
          <p className="error" role="alert">
            {error || initialError}
          </p>
        )}
        <button className="primary" disabled={busy}>
          <LogIn size={20} aria-hidden="true" />
          {busy ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}
