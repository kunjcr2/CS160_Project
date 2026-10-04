import { useCallback, useEffect, useState } from "react";

const INITIAL_STATE = {
  state: "checking",
  message: "Checking backend…",
};

export default function App() {
  const [health, setHealth] = useState(INITIAL_STATE);

  const checkHealth = useCallback(async () => {
    setHealth(INITIAL_STATE);

    try {
      const response = await fetch("/api/health");

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`);
      }

      const data = await response.json();
      const isHealthy = data.status === "healthy";

      setHealth({
        state: isHealthy ? "healthy" : "unhealthy",
        message: isHealthy ? "Backend is healthy" : "Backend reported a problem",
      });
    } catch (error) {
      setHealth({
        state: "unhealthy",
        message: "Backend is unreachable",
        detail: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }, []);

  useEffect(() => {
    checkHealth();
  }, [checkHealth]);

  return (
    <main className="page-shell">
      <section className="health-card" aria-live="polite">
        <p className="eyebrow">CS 160 · Team 4</p>
        <h1>System Health</h1>

        <div className={`status status--${health.state}`}>
          <span className="status__dot" aria-hidden="true" />
          <div>
            <strong>{health.message}</strong>
            {health.detail && <p>{health.detail}</p>}
          </div>
        </div>

        <button type="button" onClick={checkHealth} disabled={health.state === "checking"}>
          {health.state === "checking" ? "Checking…" : "Check again"}
        </button>
      </section>
    </main>
  );
}
