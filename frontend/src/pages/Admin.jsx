import { useEffect, useState } from "react";

import RoleGuard from "../components/auth/RoleGuard.jsx";
import StatusBadge from "../components/StatusBadge.jsx";
import {
  getCurrentPermissions,
  getCurrentUser,
  getHealthStatus,
  getReadinessStatus,
} from "../services/retailopsApi.js";
import {
  getSelectedDemoUserId,
  subscribeDemoUserChanged,
} from "../auth/demoUser.js";
import "../styles/api-connected-ui.css";

async function safeRequest(request) {
  try {
    const payload = await request();
    return { status: "connected", payload };
  } catch (error) {
    return { status: "error", error: error.message };
  }
}

function AdminContent({ statusCards, permissions, user }) {
  return (
    <main className="api-page">
      <section className="api-hero compact">
        <p className="eyebrow">Sprint 7 · user, roles and notifications</p>
        <h1>Admin</h1>
        <p>
          Admin view now combines platform health, selected demo identity and
          permission visibility. It remains local-first and mock-auth only.
        </p>
      </section>

      <section className="identity-panel">
        <div>
          <p className="eyebrow">Current user</p>
          <h2>{user.display_name}</h2>
          <p>{user.email}</p>
        </div>
        <StatusBadge status={user.role.replaceAll("_", " ")} />
      </section>

      <section className="permission-grid" aria-label="Current permissions">
        {permissions.map((permission) => (
          <span className="permission-pill" key={permission}>{permission}</span>
        ))}
      </section>

      <section className="endpoint-grid">
        {statusCards.map((card) => (
          <article className="endpoint-card" key={card.label}>
            <h3>{card.label}</h3>
            <StatusBadge status={card.status === "connected" ? "connected" : "error"} />
            <code>{card.endpoint}</code>
            <p>{card.status === "connected" ? "Connected to backend API" : card.error}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

function Admin() {
  const [state, setState] = useState({
    user: null,
    permissions: [],
    statusCards: [],
  });

  useEffect(() => {
    let isMounted = true;

    async function loadAdminView(userId = getSelectedDemoUserId()) {
      const [user, permissions, health, readiness] = await Promise.all([
        getCurrentUser({ userId }),
        getCurrentPermissions({ userId }),
        safeRequest(getHealthStatus),
        safeRequest(getReadinessStatus),
      ]);

      if (!isMounted) {
        return;
      }

      setState({
        user,
        permissions,
        statusCards: [
          { label: "API health", endpoint: "/health", ...health },
          { label: "API readiness", endpoint: "/ready", ...readiness },
        ],
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
        <section className="api-hero compact">
          <p className="eyebrow">Sprint 7</p>
          <h1>Loading admin context</h1>
        </section>
      </main>
    );
  }

  return (
    <RoleGuard user={state.user} requiredPermission="platform:admin">
      <AdminContent
        statusCards={state.statusCards}
        permissions={state.permissions}
        user={state.user}
      />
    </RoleGuard>
  );
}

export default Admin;
