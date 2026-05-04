import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";

import {
  emitDemoUserChanged,
  getSelectedDemoUserId,
  setSelectedDemoUserId,
} from "../auth/demoUser.js";
import UserSwitcher from "./auth/UserSwitcher.jsx";
import NotificationBell from "./notifications/NotificationBell.jsx";
import {
  getCurrentUser,
  getDemoUsers,
  getNotifications,
  hasPermission,
} from "../services/retailopsApi.js";

const NOTIFICATIONS_CHANGED_EVENT = "retailops:notifications-changed";

const navItems = [
  { label: "Dashboard", to: "/" },
  { label: "Products", to: "/products" },
  { label: "Forecasts", to: "/forecasts" },
  { label: "Anomalies", to: "/anomalies" },
  { label: "Recommendations", to: "/recommendations" },
  { label: "Admin", to: "/admin", permission: "platform:admin" },
  { label: "Profile", to: "/profile" },
];

function userCanSeeItem(user, item) {
  if (!item.permission) {
    return true;
  }

  return hasPermission(user, item.permission);
}

function Topbar() {
  const [users, setUsers] = useState([]);
  const [currentUser, setCurrentUser] = useState(null);
  const [selectedUserId, setSelectedUserId] = useState(getSelectedDemoUserId());
  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    let isMounted = true;

    async function loadIdentity() {
      try {
        const [demoUsers, user, notifications] = await Promise.all([
          getDemoUsers(),
          getCurrentUser({ userId: selectedUserId }),
          getNotifications({ userId: selectedUserId }),
        ]);

        if (!isMounted) {
          return;
        }

        setUsers(demoUsers);
        setCurrentUser(user);
        setUnreadCount(notifications?.unread_count || 0);
      } catch {
        if (!isMounted) {
          return;
        }

        setCurrentUser(null);
        setUnreadCount(0);
      }
    }

    function handleNotificationsChanged(event) {
      const changedUserId = event?.detail?.userId;

      if (changedUserId && changedUserId !== selectedUserId) {
        return;
      }

      loadIdentity();
    }

    loadIdentity();

    window.addEventListener(
      NOTIFICATIONS_CHANGED_EVENT,
      handleNotificationsChanged,
    );

    return () => {
      isMounted = false;
      window.removeEventListener(
        NOTIFICATIONS_CHANGED_EVENT,
        handleNotificationsChanged,
      );
    };
  }, [selectedUserId]);

  function handleUserChange(nextUserId) {
    setSelectedDemoUserId(nextUserId);
    setSelectedUserId(nextUserId);
    emitDemoUserChanged(nextUserId);
  }

  return (
    <nav className="topbar" aria-label="Main navigation">
      <div className="topbar-main-row">
        <NavLink className="brand" to="/" aria-label="RetailOps Platform home">
          <span className="brand-icon" aria-hidden="true">▣</span>
          <span>
            RetailOps <strong>Platform</strong>
          </span>
        </NavLink>

        <div className="topbar-tools" aria-label="User and environment controls">
          <NotificationBell unreadCount={unreadCount} />
          <UserSwitcher
            users={users}
            currentUserId={selectedUserId}
            onChange={handleUserChange}
          />
          <div className="environment-pill" aria-label="Current environment: local">
            <span className="pulse-dot"></span>
            Local Environment
          </div>
        </div>
      </div>

      <div className="nav-links" aria-label="Page sections">
        {navItems.filter((item) => userCanSeeItem(currentUser, item)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) => (isActive ? "active" : undefined)}
          >
            {item.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default Topbar;