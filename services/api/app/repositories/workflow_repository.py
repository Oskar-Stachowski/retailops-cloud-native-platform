from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row

from app.auth.roles import DemoUser
from app.db.connection import get_connection


DEMO_ROLE_TO_DB_ROLE = {
    "platform_admin": "admin",
    "operations_manager": "category_manager",
    "inventory_planner": "inventory_planner",
    "commercial_analyst": "analyst",
    "viewer": "analyst",
}


class WorkflowRepository:
    """Persistence layer for workflow status changes and action history."""

    def get_alert(self, alert_id: UUID) -> dict[str, Any] | None:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        product_id,
                        anomaly_id,
                        assigned_to_user_id,
                        alert_type,
                        severity,
                        status,
                        title,
                        recommended_action,
                        created_at,
                        updated_at
                    FROM alerts
                    WHERE id = %s;
                    """,
                    (alert_id,),
                )
                row = cursor.fetchone()

        return dict(row) if row else None

    def resolve_demo_actor_user_id(self, user: DemoUser) -> UUID:
        mapped_role = DEMO_ROLE_TO_DB_ROLE.get(user.role)

        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE login = %s
                    LIMIT 1;
                    """,
                    (user.login,),
                )
                row = cursor.fetchone()

                if row:
                    return row["id"]

                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE role = %s AND status = 'active'
                    ORDER BY login ASC
                    LIMIT 1;
                    """,
                    (mapped_role,),
                )
                row = cursor.fetchone()

                if row:
                    return row["id"]

                cursor.execute(
                    """
                    SELECT id
                    FROM users
                    WHERE status = 'active'
                    ORDER BY login ASC
                    LIMIT 1;
                    """
                )
                row = cursor.fetchone()

        if not row:
            raise LookupError("No active database user is available for workflow actions.")

        return row["id"]

    def apply_alert_workflow_action(
        self,
        *,
        alert_id: UUID,
        action: str,
        previous_status: str,
        new_status: str,
        performed_by_user_id: UUID,
        assigned_to_user_id: UUID | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE alerts
                    SET
                        status = %s,
                        assigned_to_user_id = COALESCE(%s, assigned_to_user_id),
                        updated_at = now()
                    WHERE id = %s
                    RETURNING
                        id,
                        product_id,
                        anomaly_id,
                        assigned_to_user_id,
                        alert_type,
                        severity,
                        status,
                        title,
                        recommended_action,
                        created_at,
                        updated_at;
                    """,
                    (new_status, assigned_to_user_id, alert_id),
                )
                alert = cursor.fetchone()

                if not alert:
                    raise LookupError(f"Alert {alert_id} does not exist.")

                cursor.execute(
                    """
                    INSERT INTO workflow_actions (
                        alert_id,
                        performed_by_user_id,
                        action_type,
                        comment,
                        previous_status,
                        new_status,
                        performed_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, now())
                    RETURNING
                        id,
                        alert_id,
                        performed_by_user_id,
                        action_type,
                        comment,
                        previous_status,
                        new_status,
                        performed_at,
                        created_at;
                    """,
                    (
                        alert_id,
                        performed_by_user_id,
                        action,
                        comment,
                        previous_status,
                        new_status,
                    ),
                )
                workflow_action = cursor.fetchone()
                connection.commit()

        return {
            "alert": dict(alert),
            "workflow_action": dict(workflow_action),
        }
