"""Mock notification endpoints for Sprint 7."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query

from app.api.me import to_demo_user_response
from app.api.schemas import (
    NotificationListResponse,
    NotificationReadResponse,
    NotificationResponse,
)
from app.auth.roles import (
    PERMISSION_NOTIFICATIONS_READ,
    PERMISSION_NOTIFICATIONS_WRITE,
    ROLE_INVENTORY_PLANNER,
    ROLE_OPERATIONS_MANAGER,
    ROLE_PLATFORM_ADMIN,
    get_demo_user,
    has_permission,
    require_permission,
)

router = APIRouter(tags=["notifications"])

_READ_NOTIFICATION_IDS_BY_USER: dict[str, set[str]] = {}

_DEMO_NOTIFICATIONS: list[dict[str, Any]] = [
    {
        "id": "stockout-beauty-cream",
        "title": "Stockout risk requires review",
        "message": "BEAUTY-CREAM-001 is flagged as stockout risk in the Product 360 view.",
        "category": "inventory_risk",
        "severity": "high",
        "target_role": ROLE_INVENTORY_PLANNER,
        "action_url": "/products/85710dbe-1aea-50ac-a155-fb216e12ab97",
        "created_at": datetime(2026, 5, 4, 9, 56, 43, tzinfo=timezone.utc),
    },
    {
        "id": "workflow-backlog-review",
        "title": "Operational work items waiting for triage",
        "message": "Open workflow items are visible but write actions remain out of scope.",
        "category": "workflow",
        "severity": "medium",
        "target_role": ROLE_OPERATIONS_MANAGER,
        "action_url": "/",
        "created_at": datetime(2026, 5, 4, 9, 58, 0, tzinfo=timezone.utc),
    },
    {
        "id": "admin-readiness-check",
        "title": "Platform readiness is available",
        "message": "The admin page can verify API health and readiness using live endpoints.",
        "category": "platform",
        "severity": "info",
        "target_role": ROLE_PLATFORM_ADMIN,
        "action_url": "/admin",
        "created_at": datetime(2026, 5, 4, 10, 0, 0, tzinfo=timezone.utc),
    },
]


def _notification_visible_for_user(user, notification: dict[str, Any]) -> bool:
    """Platform admins can see everything; other users see role-targeted items."""

    if has_permission(user, "platform:admin"):
        return True

    return notification["target_role"] == user.role


def _read_ids_for_user(user_id: str) -> set[str]:
    return _READ_NOTIFICATION_IDS_BY_USER.setdefault(user_id, set())


def _to_response(user_id: str, notification: dict[str, Any]) -> NotificationResponse:
    read_ids = _read_ids_for_user(user_id)
    is_read = notification["id"] in read_ids

    return NotificationResponse(
        id=notification["id"],
        title=notification["title"],
        message=notification["message"],
        category=notification["category"],
        severity=notification["severity"],
        status="read" if is_read else "unread",
        target_role=notification["target_role"],
        action_url=notification["action_url"],
        created_at=notification["created_at"],
        read_at=datetime.now(timezone.utc) if is_read else None,
    )


def _visible_notifications_for_user(user) -> list[NotificationResponse]:
    visible = [
        notification
        for notification in _DEMO_NOTIFICATIONS
        if _notification_visible_for_user(user, notification)
    ]

    return [_to_response(user.id, notification) for notification in visible]


@router.get("/notifications", response_model=NotificationListResponse)
def list_notifications(
    user_id: str | None = Query(default=None, description="Local demo user id."),
) -> NotificationListResponse:
    """Return mock notifications visible to the selected demo user."""

    user = get_demo_user(user_id)
    require_permission(user, PERMISSION_NOTIFICATIONS_READ)

    items = _visible_notifications_for_user(user)
    unread_count = sum(1 for item in items if item.status == "unread")

    return NotificationListResponse(
        items=items,
        unread_count=unread_count,
        total_count=len(items),
        user=to_demo_user_response(user),
    )


@router.post(
    "/notifications/{notification_id}/read",
    response_model=NotificationReadResponse,
)
def mark_notification_read(
    notification_id: str,
    user_id: str | None = Query(default=None, description="Local demo user id."),
) -> NotificationReadResponse:
    """Mark a visible mock notification as read for the selected demo user."""

    user = get_demo_user(user_id)
    require_permission(user, PERMISSION_NOTIFICATIONS_WRITE)

    visible_notifications = _visible_notifications_for_user(user)
    matching_notification = next(
        (
            notification
            for notification in visible_notifications
            if notification.id == notification_id
        ),
        None,
    )

    if matching_notification is None:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "notification_not_found",
                "message": "Notification is not visible for this demo user.",
            },
        )

    _read_ids_for_user(user.id).add(notification_id)
    items = _visible_notifications_for_user(user)
    updated_notification = next(
        notification for notification in items if notification.id == notification_id
    )
    unread_count = sum(1 for notification in items if notification.status == "unread")

    return NotificationReadResponse(
        notification=updated_notification,
        unread_count=unread_count,
    )
