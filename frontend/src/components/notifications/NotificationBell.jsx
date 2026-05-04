import { NavLink } from "react-router-dom";

function NotificationBell({ unreadCount = 0 }) {
  const label = unreadCount === 1 ? "1 unread notification" : `${unreadCount} unread notifications`;

  return (
    <NavLink className="notification-bell" to="/profile" aria-label={label}>
      <span aria-hidden="true">🔔</span>
      <strong>{unreadCount}</strong>
    </NavLink>
  );
}

export default NotificationBell;
