import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import MetricCard from "../components/MetricCard.jsx";
import PageHeader from "../components/PageHeader";
import StatusBadge from "../components/StatusBadge.jsx";
import {
  getCurrentPermissions,
  getCurrentUserContext,
  getNotifications,
  markNotificationRead,
} from "../services/retailopsApi.js";
import {
  getSelectedDemoUserId,
  subscribeDemoUserChanged,
} from "../auth/demoUser.js";
import "../styles/api-connected-ui.css";

const NOTIFICATIONS_CHANGED_EVENT = "retailops:notifications-changed";

function emitNotificationsChanged(userId) {
  window.dispatchEvent(
    new CustomEvent(NOTIFICATIONS_CHANGED_EVENT, {
      detail: { userId },
    }),
  );
}

function formatRole(role) {
  return String(role || "unknown").replaceAll("_", " ");
}

function formatAuthMode(authMode) {
  return String(authMode || "local_mock").replaceAll("_", " ");
}

function getInitials(displayName) {
  return String(displayName || "Demo User")
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part.at(0).toUpperCase())
    .join("");
}

function permissionSummary(permissions) {
  if (permissions.includes("platform:admin")) {
    return "Full demo admin scope";
  }

  if (permissions.length === 0) {
    return "No explicit permissions";
  }

  return `${permissions.length} permission${permissions.length === 1 ? "" : "s"} assigned`;
}

function Profile() {
  const [state, setState] = useState({
    authMode: "local_mock",
    permissions: [],
    notifications: [],
    scopeBoundary: "",
    unreadCount: 0,
    user: null,
  });

  async function loadProfile(userId = getSelectedDemoUserId()) {
    const [userContext, permissions, notificationsPayload] = await Promise.all([
      getCurrentUserContext({ userId }),
      getCurrentPermissions({ userId }),
      getNotifications({ userId }),
    ]);

    setState({
      authMode: userContext?.auth_mode || "local_mock",
      permissions,
      notifications: notificationsPayload?.items || [],
      scopeBoundary: userContext?.scope_boundary || "",
      unreadCount: notificationsPayload?.unread_count || 0,
      user: {
        ...(userContext?.user || userContext),
        permissions,
      },
    });
  }

  useEffect(() => {
    let isMounted = true;

    async function guardedLoad(userId) {
      if (!isMounted) {
        return;
      }

      await loadProfile(userId);
    }

    guardedLoad(getSelectedDemoUserId());
    const unsubscribe = subscribeDemoUserChanged(guardedLoad);

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  async function handleMarkRead(notificationId) {
    const userId = getSelectedDemoUserId();

    await markNotificationRead(notificationId, { userId });
    await loadProfile(userId);
    emitNotificationsChanged(userId);
  }

  if (!state.user) {
    return (
      <main className="api-page">
        <PageHeader
          eyebrow="User profile"
          title="Loading profile"
          description="Fetching selected demo identity, role, permissions and notifications."
        />
      </main>
    );
  }

  return (
    <main className="api-page profile-context-page">
      <PageHeader
        eyebrow="User profile"
        title={state.user.display_name}
        description="Identity, role, permission scope and local notification context for the selected demo user. Platform health and governance checks live in Admin."
      />

      <section className="metrics-grid" aria-label="Profile summary">
        <MetricCard
          label="Role"
          value={formatRole(state.user.role)}
          helper="Selected local demo persona"
          status="Identity"
        />
        <MetricCard
          label="Permissions"
          value={state.permissions.length}
          helper={permissionSummary(state.permissions)}
          status="Access"
          tone={state.permissions.length > 0 ? "positive" : "warning"}
        />
        <MetricCard
          label="Unread notifications"
          value={state.unreadCount}
          helper="User-specific mock notification queue"
          status="Inbox"
          tone={state.unreadCount > 0 ? "warning" : "positive"}
        />
        <MetricCard
          label="Business area"
          value={state.user.business_area || "—"}
          helper={state.user.team || "No team assigned"}
          status="Context"
        />
      </section>

      <section className="identity-panel profile-identity-panel">
        <div className="profile-avatar" aria-hidden="true">
          {getInitials(state.user.display_name)}
        </div>
        <div className="profile-identity-panel__details">
          <p className="eyebrow">Identity</p>
          <h2>{state.user.display_name}</h2>
          <p>{state.user.email}</p>
          <dl className="profile-kv-list">
            <div>
              <dt>Login</dt>
              <dd>{state.user.login || state.user.id}</dd>
            </div>
            <div>
              <dt>Team</dt>
              <dd>{state.user.team || "—"}</dd>
            </div>
            <div>
              <dt>Auth mode</dt>
              <dd>{formatAuthMode(state.authMode)}</dd>
            </div>
          </dl>
        </div>
        <StatusBadge status={formatRole(state.user.role)} />
      </section>

      <section className="profile-section">
        <header className="profile-section__header">
          <div>
            <p className="eyebrow">Permission scope</p>
            <h2>Role permissions</h2>
            <p>
              These permissions drive local role-aware UI boundaries. They are intentionally scoped
              to the selected demo user.
            </p>
          </div>
          <StatusBadge status={`${state.permissions.length} permissions`} />
        </header>
        <div className="permission-grid" aria-label="Current permissions">
          {state.permissions.map((permission) => (
            <span className="permission-pill" key={permission}>
              {permission}
            </span>
          ))}
        </div>
      </section>

      <section className="table-card">
        <header className="table-card__header profile-table-header">
          <div>
            <p className="eyebrow">Notifications</p>
            <h2>User notification queue</h2>
            <p>Local mock notifications visible to the selected demo user.</p>
          </div>
          <StatusBadge status={`${state.unreadCount} unread`} />
        </header>

        <table>
          <thead>
            <tr>
              <th>Notification</th>
              <th>Severity</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>

          <tbody>
            {state.notifications.length === 0 ? (
              <tr>
                <td colSpan="4">
                  No notifications returned for this user.
                </td>
              </tr>
            ) : (
              state.notifications.map((notification) => (
                <tr key={notification.id}>
                  <td>
                    <strong>{notification.title}</strong>
                    <p>{notification.message}</p>
                  </td>
                  <td>
                    <StatusBadge status={notification.severity} />
                  </td>
                  <td>
                    <StatusBadge status={notification.status} />
                  </td>
                  <td>
                    {notification.status === "unread" ? (
                      <button
                        className="inline-action"
                        type="button"
                        onClick={() => handleMarkRead(notification.id)}
                      >
                        Mark read
                      </button>
                    ) : (
                      <NavLink className="inline-link" to={notification.action_url || "/"}>
                        Open
                      </NavLink>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>

      {state.scopeBoundary ? (
        <section className="profile-auth-note">
          <p className="eyebrow">Auth boundary</p>
          <p>{state.scopeBoundary}</p>
        </section>
      ) : null}
    </main>
  );
}

export default Profile;
