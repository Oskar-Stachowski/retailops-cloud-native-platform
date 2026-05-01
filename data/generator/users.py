from __future__ import annotations

from data.generator.common import deterministic_uuid
from data.generator.scenarios import USER_BLUEPRINTS


def generate_users() -> list[dict[str, str]]:
    users: list[dict[str, str]] = []

    for item in USER_BLUEPRINTS:
        login = item["login"]
        users.append(
            {
                "id": deterministic_uuid("user", login),
                "login": login,
                "display_name": item["display_name"],
                "role": item["role"],
                "team": item["team"],
                "status": "active",
            }
        )

    return users


def user_by_role(users: list[dict[str, str]], role: str) -> dict[str, str]:
    return next(user for user in users if user["role"] == role)
