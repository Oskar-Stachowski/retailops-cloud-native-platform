import { useCallback, useEffect, useState } from "react";
import ErrorState from "../components/ErrorState";
import LoadingState from "../components/LoadingState";
import StatusBadge from "../components/StatusBadge";
import { getHealthStatus, getReadinessStatus } from "../services/retailopsApi";
import "../styles/api-connected-ui.css";

function PlatformStatusCard({ title, result }) {
  return (
    <article className="source-card">
      <strong>{title}</strong>

      <StatusBadge status={result.ok ? "connected" : "unavailable"}>
        {result.ok ? "connected" : "unavailable"}
      </StatusBadge>

      <code>{result.path}</code>

      <p>{result.ok ? JSON.stringify(result.data) : result.error?.message}</p>
    </article>
  );
}

async function fetchPlatformStatus() {
  const [health, readiness] = await Promise.all([
    getHealthStatus(),
    getReadinessStatus(),
  ]);

  return { health, readiness };
}

export default function Admin() {
  const [state, setState] = useState({
    loading: true,
    error: null,
    health: null,
    readiness: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function loadInitialStatus() {
      try {
        const { health, readiness } = await fetchPlatformStatus();

        if (isMounted) {
          setState({
            loading: false,
            error: null,
            health,
            readiness,
          });
        }
      } catch (error) {
        if (isMounted) {
          setState({
            loading: false,
            error,
            health: null,
            readiness: null,
          });
        }
      }
    }

    loadInitialStatus();

    return () => {
      isMounted = false;
    };
  }, []);

  const handleRetry = useCallback(async () => {
    setState((current) => ({
      ...current,
      loading: true,
      error: null,
    }));

    try {
      const { health, readiness } = await fetchPlatformStatus();

      setState({
        loading: false,
        error: null,
        health,
        readiness,
      });
    } catch (error) {
      setState({
        loading: false,
        error,
        health: null,
        readiness: null,
      });
    }
  }, []);

  if (state.loading) {
    return <LoadingState title="Loading platform status" />;
  }

  if (state.error) {
    return <ErrorState message={state.error.message} onRetry={handleRetry} />;
  }

  return (
    <main className="api-page">
      <header className="api-page__header">
        <p className="eyebrow">Platform status</p>
        <h1>Admin</h1>
        <p>
          Admin view uses health and readiness endpoints instead of static
          placeholder status.
        </p>
      </header>

      <section className="source-grid">
        <PlatformStatusCard title="API health" result={state.health} />
        <PlatformStatusCard title="API readiness" result={state.readiness} />
      </section>
    </main>
  );
}