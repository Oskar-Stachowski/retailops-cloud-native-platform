"""Mock identity endpoints for Sprint 7."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.api.schemas import (
    CurrentUserResponse,
    DemoUserListResponse,
    DemoUserResponse,
    PermissionListResponse,
)
from app.auth.roles import DEMO_USERS, DemoUser, get_demo_user, get_user_permissions

router = APIRouter(tags=["identity"])


def to_demo_user_response(user: DemoUser) -> DemoUserResponse:
    """Map an internal demo user to the public API contract."""
    return DemoUserResponse(
        id=user.id,
        login=user.login,
        display_name=user.display_name,
        email=user.email,
        role=user.role,
        team=user.team,
        business_area=user.business_area,
        permissions=get_user_permissions(user),
    )


@router.get("/users/demo")
def list_demo_users() -> DemoUserListResponse:
    """List selectable local demo users for the frontend switcher."""
    items = [to_demo_user_response(user) for user in DEMO_USERS.values()]
    return DemoUserListResponse(items=items, default_user_id="platform-admin")


@router.get("/me")
def get_current_user(
    user_id: Annotated[str | None, Query(description="Local demo user id.")] = None,
) -> CurrentUserResponse:
    """Return the currently selected local demo user."""
    user = get_demo_user(user_id)
    return CurrentUserResponse(
        user=to_demo_user_response(user),
        auth_mode="local_mock",
        scope_boundary=(
            "Sprint 7 uses mock identity only. It does not implement real login, "
            "JWT validation, SSO, sessions or production RBAC enforcement."
        ),
    )


@router.get("/me/permissions")
def get_current_permissions(
    user_id: Annotated[str | None, Query(description="Local demo user id.")] = None,
) -> PermissionListResponse:
    """Return permissions assigned to the current local demo user."""
    user = get_demo_user(user_id)
    return PermissionListResponse(
        user_id=user.id,
        role=user.role,
        permissions=get_user_permissions(user),
    )
