import { useEffect, useMemo, useState } from "react";

import MetricCard from "../components/MetricCard.jsx";
import PageHeader from "../components/PageHeader";
import RoleGuard from "../components/auth/RoleGuard.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import { EXTENDED_API_TIMEOUT_MS } from "../services/apiClient.js";
import {
  getCurrentPermissions,
  getCurrentUserContext,
  getHealthStatus,
  getReadinessStatus,
} from "../services/retailopsApi.js";
import {
  getSelectedDemoUserId,
  subscribeDemoUserChanged,
} from "../auth/demoUser.js";
import "../styles/api-connected-ui.css";

const ADMIN_SCOPE_ITEMS = [
  "Platform health",
  "Backend readiness",
  "Environment visibility",
  "API status",
  "Local mock auth boundary",
];

function formatRole(role) {
  return String(role || "unknown").replaceAll("_", " ");
}

function formatAuthMode(authMode) {
  return String(authMode || "local_mock").replaceAll("_", " ");
}

function getStatusTone(status) {
  return status === "connected" ? "positive" : "risk";
}

function getStatusLabel(status) {
  return status === "connected" ? "connected" : "error";
}

async function safeEndpointRequest(request) {
  try {
    const result = await request();

    if (result?.ok) {
      return {
        status: "connected",
        path: result.path,
        payload: result.data || {},
        error: null,
      };
    }

    return {
      status: "error",
      path: result?.path,
      payload: {},
      error: result?.error?.message || "Endpoint is not available.",
    };
  } catch (error) {
    return {
      status: "error",
      path: null,
      payload: {},
      error: error.message,
    };
  }
}

function buildPlatformSummary(statusCards, authMode) {
  const health = statusCards.find((card) => card.key === "health");
  const readiness = statusCards.find((card) => card.key === "readiness");
  const connectedCount = statusCards.filter((card) => card.status === "connected").length;
  const environment =
    readiness?.payload?.environment || health?.payload?.environment || "local";
  const database = readiness?.payload?.database || "unknown";

  return {
    healthStatus: health?.status || "error",
    readinessStatus: readiness?.status || "error",
    environment,
    database,
    connectedCount,
    totalEndpoints: statusCards.length,
    authMode: formatAuthMode(authMode),
  };
}

function EndpointCard({ card }) {
  const service = card.payload?.service || "retailops-api";
  const environment = card.payload?.environment || "—";
  const database = card.payload?.database;

  return (
    <article className="endpoint-card admin-endpoint-card">
      <div className="admin-card-heading">
        <div>
          <p className="eyebrow">{card.scope}</p>
          <h3>{card.label}</h3>
        </div>
        <StatusBadge status={getStatusLabel(card.status)} />
      </div>
      <code>{card.path || card.endpoint}</code>
      <p>{card.status === "connected" ? card.successMessage : card.error}</p>
      <dl className="admin-kv-list">
        <div>
          <dt>Service</dt>
          <dd>{service}</dd>
        </div>
        <div>
          <dt>Environment</dt>
          <dd>{environment}</dd>
        </div>
        {database ? (
          <div>
            <dt>Database</dt>
            <dd>{database}</dd>
          </div>
        ) : null}
      </dl>
    </article>
  );
}

function AdminContent({ authMode, permissions, scopeBoundary, statusCards, user }) {
  const platformSummary = useMemo(
    () => buildPlatformSummary(statusCards, authMode),
    [authMode, statusCards],
  );

  return (
    <main className="api-page admin-readiness-page">
      <PageHeader
        eyebrow="Platform administration"
        title="Admin readiness"
        description="Operational view for platform health, backend readiness, runtime environment and the local mock-auth governance boundary. User identity details live in Profile."
      />

      <section className="metrics-grid" aria-label="Platform readiness summary">
        <MetricCard
          label="Platform health"
          value={getStatusLabel(platformSummary.healthStatus)}
          helper="Derived from /health"
          status="API"
          tone={getStatusTone(platformSummary.healthStatus)}
        />
        <MetricCard
          label="Backend readiness"
          value={getStatusLabel(platformSummary.readinessStatus)}
          helper={`Database: ${platformSummary.database}`}
          status="Ready"
          tone={getStatusTone(platformSummary.readinessStatus)}
        />
        <MetricCard
          label="Environment"
          value={platformSummary.environment}
          helper="Runtime context exposed by backend probes"
          status="Runtime"
        />
        <MetricCard
          label="API status"
          value={`${platformSummary.connectedCount}/${platformSummary.totalEndpoints}`}
          helper="Probe endpoints connected"
          status="Checks"
          tone={
            platformSummary.connectedCount === platformSummary.totalEndpoints
              ? "positive"
              : "warning"
          }
        />
      </section>

      <section className="admin-governance-panel">
        <div className="admin-governance-panel__main">
          <p className="eyebrow">Governance boundary</p>
          <h2>Admin is for platform readiness, not user profile data</h2>
          <p>
            This page verifies whether the local platform is reachable and ready to support
            operational workflows. It intentionally keeps identity details minimal because Profile
            owns user, role, permission and notification context.
          </p>
        </div>
        <dl className="admin-kv-list admin-kv-list--cards">
          <div>
            <dt>Current operator</dt>
            <dd>{user.display_name}</dd>
          </div>
          <div>
            <dt>Role gate</dt>
            <dd>{formatRole(user.role)}</dd>
          </div>
          <div>
            <dt>Auth mode</dt>
            <dd>{platformSummary.authMode}</dd>
          </div>
          <div>
            <dt>Required permission</dt>
            <dd>platform:admin</dd>
          </div>
        </dl>
      </section>

      <section className="admin-scope-grid" aria-label="Admin responsibilities">
        {ADMIN_SCOPE_ITEMS.map((item) => (
          <span className="admin-scope-pill" key={item}>{item}</span>
        ))}
      </section>

      <section className="endpoint-grid" aria-label="Platform endpoint status">
        {statusCards.map((card) => (
          <EndpointCard card={card} key={card.key} />
        ))}
      </section>

      <section className="admin-auth-warning">
        <div>
          <p className="eyebrow">Local mock auth warning</p>
          <h2>Demo governance only</h2>
          <p>
            {scopeBoundary ||
              "This local environment uses mock identity only. It is useful for portfolio evidence, but does not replace production SSO, JWT validation or centralized RBAC enforcement."}
          </p>
        </div>
        <StatusBadge status={permissions.includes("platform:admin") ? "admin" : "limited"} />
      </section>
    </main>
  );
}

function Admin() {
  const [state, setState] = useState({
    authMode: "local_mock",
    permissions: [],
    scopeBoundary: "",
    statusCards: [],
    user: null,
  });

  useEffect(() => {
    let isMounted = true;

    async function loadAdminView(userId = getSelectedDemoUserId()) {
      const [userContext, permissions, health, readiness] = await Promise.all([
        getCurrentUserContext({ userId }),
        getCurrentPermissions({ userId }),
        safeEndpointRequest(() => getHealthStatus({ timeoutMs: EXTENDED_API_TIMEOUT_MS })),
        safeEndpointRequest(() => getReadinessStatus({ timeoutMs: EXTENDED_API_TIMEOUT_MS })),
      ]);

      if (!isMounted) {
        return;
      }

      const user = userContext?.user || userContext;

      setState({
        authMode: userContext?.auth_mode || "local_mock",
        permissions,
        scopeBoundary: userContext?.scope_boundary || "",
        statusCards: [
          {
            key: "health",
            label: "API health",
            scope: "Platform health",
            endpoint: "/health",
            successMessage: "Backend service is reachable.",
            ...health,
          },
          {
            key: "readiness",
            label: "Backend readiness",
            scope: "Database readiness",
            endpoint: "/ready",
            successMessage: "Backend service and database are ready.",
            ...readiness,
          },
        ],
        user: {
          ...user,
          permissions,
        },
      });
    }

    loadAdminView();
    const unsubscribe = subscribeDemoUserChanged(loadAdminView);

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  if (!state.user) {
    return (
      <main className="api-page">
        <PageHeader
          eyebrow="Platform administration"
          title="Loading admin readiness"
          description="Fetching selected demo identity, governance boundary and platform probes."
        />
      </main>
    );
  }

  return (
    <RoleGuard user={state.user} requiredPermission="platform:admin">
      <AdminContent
        authMode={state.authMode}
        permissions={state.permissions}
        scopeBoundary={state.scopeBoundary}
        statusCards={state.statusCards}
        user={state.user}
      />
    </RoleGuard>
  );
}

export default Admin;
