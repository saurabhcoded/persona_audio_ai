import { useEffect, useState } from "react";
import { apiGet } from "./api.js";

export default function App() {
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  const check = async () => {
    setLoading(true);
    setError(null);
    try {
      setHealth(await apiGet("/health"));
    } catch (e) {
      setHealth(null);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    check();
  }, []);

  const status = loading ? "checking" : error ? "down" : "up";

  return (
    <main className="container">
      <header>
        <h1>Fish Audio</h1>
        <p className="muted">React + Vite frontend for the FastAPI backend.</p>
      </header>

      <section className="card">
        <div className="card-head">
          <h2>API status</h2>
          <span className={`badge ${status}`}>{status}</span>
        </div>

        {error && <p className="error">Could not reach the API: {error}</p>}

        {health && (
          <dl className="grid">
            <dt>App</dt>
            <dd>{health.app}</dd>
            <dt>Version</dt>
            <dd>{health.version}</dd>
            <dt>Environment</dt>
            <dd>{health.environment}</dd>
          </dl>
        )}

        <button onClick={check} disabled={loading}>
          {loading ? "Checking…" : "Refresh"}
        </button>
      </section>
    </main>
  );
}
