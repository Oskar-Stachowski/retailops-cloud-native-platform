"""Mock user and role model for Sprint 7.

This module is intentionally local-first. It does not implement real
authentication, sessions, JWT, OAuth or IAM. The goal is to make role-aware UI,
OpenAPI contracts and access boundaries visible before production-grade auth is
introduced in a later sprint.
"""

from dataclasses import dataclass
from typing import Final

from fastapi import HTTPException, status


ROLE_PLATFORM_ADMIN: Final = "platform_admin"
ROLE_OPERATIONS_MANAGER: Final = "operations_manager"
ROLE_INVENTORY_PLANNER: Final = "inventory_planner"
ROLE_COMMERCIAL_ANALYST: Final = "commercial_analyst"
ROLE_VIEWER: Final = "viewer"

PERMISSION_PLATFORM_ADMIN: Final = "platform:admin"
PERMISSION_DASHBOARD_READ: Final = "dashboard:read"
PERMISSION_PRODUCTS_READ: Final = "products:read"
PERMISSION_FORECASTS_READ: Final = "forecasts:read"
PERMISSION_INVENTORY_READ: Final = "inventory:read"
PERMISSION_WORKFLOW_READ: Final = "workflow:read"
PERMISSION_NOTIFICATIONS_READ: Final = "notifications:read"
PERMISSION_NOTIFICATIONS_WRITE: Final = "notifications:write"

DEFAULT_DEMO_USER_ID: Final = "platform-admin"


@dataclass(frozen=True)
class DemoUser:
    """Small internal representation of a demo user."""

    id: str
    login: str
    display_name: str
    email: str
    role: str
    team: str
    business_area: str


PERMISSIONS_BY_ROLE: Final[dict[str, list[str]]] = {
    ROLE_PLATFORM_ADMIN: [
        PERMISSION_PLATFORM_ADMIN,
        PERMISSION_DASHBOARD_READ,
        PERMISSION_PRODUCTS_READ,
        PERMISSION_FORECASTS_READ,
        PERMISSION_INVENTORY_READ,
        PERMISSION_WORKFLOW_READ,
        PERMISSION_NOTIFICATIONS_READ,
        PERMISSION_NOTIFICATIONS_WRITE,
    ],
    ROLE_OPERATIONS_MANAGER: [
        PERMISSION_DASHBOARD_READ,
        PERMISSION_PRODUCTS_READ,
        PERMISSION_FORECASTS_READ,
        PERMISSION_INVENTORY_READ,
        PERMISSION_WORKFLOW_READ,
        PERMISSION_NOTIFICATIONS_READ,
        PERMISSION_NOTIFICATIONS_WRITE,
    ],
    ROLE_INVENTORY_PLANNER: [
        PERMISSION_DASHBOARD_READ,
        PERMISSION_PRODUCTS_READ,
        PERMISSION_FORECASTS_READ,
        PERMISSION_INVENTORY_READ,
        PERMISSION_WORKFLOW_READ,
        PERMISSION_NOTIFICATIONS_READ,
        PERMISSION_NOTIFICATIONS_WRITE,
    ],
    ROLE_COMMERCIAL_ANALYST: [
        PERMISSION_DASHBOARD_READ,
        PERMISSION_PRODUCTS_READ,
        PERMISSION_FORECASTS_READ,
        PERMISSION_NOTIFICATIONS_READ,
        PERMISSION_NOTIFICATIONS_WRITE,
    ],
    ROLE_VIEWER: [
        PERMISSION_DASHBOARD_READ,
        PERMISSION_PRODUCTS_READ,
    ],
}

DEMO_USERS: Final[dict[str, DemoUser]] = {
    "platform-admin": DemoUser(
        id="platform-admin",
        login="platform.admin",
        display_name="Platform Admin",
        email="platform.admin@retailops.local",
        role=ROLE_PLATFORM_ADMIN,
        team="Platform Engineering",
        business_area="Platform Governance",
    ),
    "ops-manager": DemoUser(
        id="ops-manager",
        login="ops.manager",
        display_name="Operations Manager",
        email="ops.manager@retailops.local",
        role=ROLE_OPERATIONS_MANAGER,
        team="Retail Operations",
        business_area="Operational Control",
    ),
    "inventory-planner": DemoUser(
        id="inventory-planner",
        login="inventory.planner",
        display_name="Inventory Planner",
        email="inventory.planner@retailops.local",
        role=ROLE_INVENTORY_PLANNER,
        team="Inventory Planning",
        business_area="Stock Availability",
    ),
    "commercial-analyst": DemoUser(
        id="commercial-analyst",
        login="commercial.analyst",
        display_name="Commercial Analyst",
        email="commercial.analyst@retailops.local",
        role=ROLE_COMMERCIAL_ANALYST,
        team="Commercial Analytics",
        business_area="Revenue and Margin",
    ),
    "read-only-viewer": DemoUser(
        id="read-only-viewer",
        login="read.only",
        display_name="Read-only Viewer",
        email="read.only@retailops.local",
        role=ROLE_VIEWER,
        team="Executive Stakeholders",
        business_area="Read-only Visibility",
    ),
}


def get_permissions_for_role(role: str) -> list[str]:
    """Return the explicit permission list assigned to a role."""

    return PERMISSIONS_BY_ROLE.get(role, [])


def get_user_permissions(user: DemoUser) -> list[str]:
    """Return permissions for a concrete demo user."""

    return get_permissions_for_role(user.role)


def has_permission(user: DemoUser, permission: str) -> bool:
    """Check whether a demo user has a specific permission."""

    return permission in get_user_permissions(user)


def get_demo_user(user_id: str | None = None) -> DemoUser:
    """Resolve a demo user from a query parameter.

    The default is the platform admin because this keeps local development
    permissive while still allowing role boundaries to be tested.
    """

    resolved_user_id = user_id or DEFAULT_DEMO_USER_ID

    try:
        return DEMO_USERS[resolved_user_id]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "demo_user_not_found",
                "message": f"Demo user '{resolved_user_id}' does not exist.",
            },
        ) from exc


def require_permission(user: DemoUser, permission: str) -> None:
    """Raise 403 if the user does not have the required permission."""

    if has_permission(user, permission):
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "permission_denied",
            "message": f"Permission '{permission}' is required for this action.",
        },
    )
