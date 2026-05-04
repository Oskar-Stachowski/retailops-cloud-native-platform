import { hasPermission } from "../../services/retailopsApi.js";

function RoleGuard({ user, requiredPermission, allowedRoles = [], children }) {
  const hasRequiredPermission = requiredPermission
    ? hasPermission(user, requiredPermission)
    : true;
  const hasAllowedRole = allowedRoles.length > 0
    ? allowedRoles.includes(user?.role)
    : true;

  if (user && hasRequiredPermission && hasAllowedRole) {
    return children;
  }

  return (
    <section className="access-boundary-card" aria-label="Access boundary">
      <p className="eyebrow">Sprint 7 access boundary</p>
      <h2>Role-aware access boundary</h2>
      <p>
        This screen is intentionally protected by a local mock permission check.
        Select a platform admin demo user to access this view.
      </p>
      <dl className="access-boundary-details">
        <div>
          <dt>Current role</dt>
          <dd>{user?.role || "Loading user context"}</dd>
        </div>
        <div>
          <dt>Required permission</dt>
          <dd>{requiredPermission || "—"}</dd>
        </div>
      </dl>
    </section>
  );
}

export default RoleGuard;
