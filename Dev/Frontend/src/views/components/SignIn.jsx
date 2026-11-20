import { useState } from "react";
import { HeartPulse, LogIn } from "lucide-react";
import { errorMessage } from "../../models/api.js";

export default function SignIn({ api, onSignIn, initialError }) {
  const [method, setMethod] = useState("pair");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event) {
    event.preventDefault();
    if (busy) return;
    const data = new FormData(event.currentTarget);
    if (method === "register" && data.get("password") !== data.get("confirmPassword")) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const values = method === "pair"
        ? { code: data.get("code").trim() }
        : { email: data.get("email").trim(), password: data.get("password") };
      onSignIn(await (method === "register"
        ? api.registerCaregiver({ ...values, display_name: data.get("displayName").trim() })
        : api.signIn(method, values)));
    } catch (error) {
      if (method === "register" && error.status === 409) {
        setError("This email already has an account. Sign in instead.");
      } else if (error.status === 401) {
        setError(
          method === "pair"
            ? "That pairing code is invalid or expired. Ask your caregiver for a new code."
            : "The email or password is incorrect.",
        );
      } else {
        setError(errorMessage(error));
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="sign-in">
      <span className="brand-mark"><HeartPulse size={25} aria-hidden="true" /></span>
      <h1>Care Companion</h1>
      <p className="sign-in-intro">A little help with the care that matters to you.</p>
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
        <button
          className="secondary"
          aria-pressed={method === "register"}
          disabled={busy}
          onClick={() => {
            setMethod("register");
            setError("");
          }}
        >
          Create caregiver account
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
            {method === "register" && (
              <label>
                Your name
                <input name="displayName" autoComplete="name" required maxLength={120} disabled={busy} />
              </label>
            )}
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
                minLength={method === "register" ? 12 : undefined}
                disabled={busy}
              />
            </label>
            {method === "register" && (
              <label>
                Confirm password
                <input name="confirmPassword" type="password" autoComplete="new-password"
                  required minLength={12} disabled={busy} />
              </label>
            )}
          </>
        )}
        {(error || initialError) && (
          <p className="error" role="alert">
            {error || initialError}
          </p>
        )}
        <button className="primary" disabled={busy}>
          <LogIn size={20} aria-hidden="true" />
          {busy ? "Please wait..." : method === "register" ? "Create account" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
