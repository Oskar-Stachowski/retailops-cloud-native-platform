import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import StatusBadge from "../components/StatusBadge.jsx";
import {
  getCurrentPermissions,
  getCurrentUser,
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

function Profile() {
  const [state, setState] = useState({
    user: null,
    permissions: [],
    notifications: [],
    unreadCount: 0,
  });

  async function loadProfile(userId = getSelectedDemoUserId()) {
    const [user, permissions, notificationsPayload] = await Promise.all([
      getCurrentUser({ userId }),
      getCurrentPermissions({ userId }),
      getNotifications({ userId }),
    ]);

    setState({
      user,
      permissions,
      notifications: notificationsPayload?.items || [],
      unreadCount: notificationsPayload?.unread_count || 0,
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
        <section className="api-hero compact">
          <p className="eyebrow">Sprint 7</p>
          <h1>Loading profile</h1>
        </section>
      </main>
    );
  }

  return (
    <main className="api-page">
      <section className="api-hero compact">
        <p className="eyebrow">Sprint 7 · local mock identity</p>
        <h1>{state.user.display_name}</h1>
        <p>{state.user.email}</p>
      </section>

      <section className="identity-panel">
        <div>
          <p className="eyebrow">Role</p>
          <h2>{state.user.role.replaceAll("_", " ")}</h2>
          <p>{state.user.team} · {state.user.business_area}</p>
        </div>
        <StatusBadge status={`${state.unreadCount} unread`} />
      </section>

      <section className="permission-grid" aria-label="Current permissions">
        {state.permissions.map((permission) => (
          <span className="permission-pill" key={permission}>
            {permission}
          </span>
        ))}
      </section>

      <section className="table-card">
        <header>
          <h2>Notifications</h2>
          <p>Local mock notifications visible to the selected demo user.</p>
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
    </main>
  );
}

export default Profile;