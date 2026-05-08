from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

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

    def get_recommendation(self, recommendation_id: UUID) -> dict[str, Any] | None:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        product_id,
                        forecast_id,
                        anomaly_id,
                        alert_id,
                        recommendation_type,
                        recommended_action,
                        rationale,
                        status,
                        generated_at,
                        expires_at,
                        created_at
                    FROM recommendations
                    WHERE id = %s;
                    """,
                    (recommendation_id,),
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

    def get_workflow_audit_log(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        idempotency_key: str,
    ) -> dict[str, Any] | None:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    SELECT
                        id,
                        entity_type,
                        entity_id,
                        action_type,
                        performed_by_user_id,
                        assigned_to_user_id,
                        previous_status,
                        new_status,
                        comment,
                        idempotency_key,
                        source,
                        details,
                        performed_at,
                        created_at
                    FROM workflow_audit_log
                    WHERE entity_type = %s
                      AND entity_id = %s
                      AND idempotency_key = %s
                    LIMIT 1;
                    """,
                    (entity_type, entity_id, idempotency_key),
                )
                row = cursor.fetchone()

        return dict(row) if row else None

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
        idempotency_key: str | None = None,
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
                audit_log = self._insert_workflow_audit_log(
                    cursor,
                    entity_type="alert",
                    entity_id=alert_id,
                    action=action,
                    previous_status=previous_status,
                    new_status=new_status,
                    performed_by_user_id=performed_by_user_id,
                    assigned_to_user_id=assigned_to_user_id,
                    comment=comment,
                    idempotency_key=idempotency_key,
                    details={
                        "workflow_action_id": str(workflow_action["id"]),
                    },
                )
                connection.commit()

        return {
            "alert": dict(alert),
            "workflow_action": dict(workflow_action),
            "audit_log": dict(audit_log),
        }

    def apply_recommendation_workflow_action(
        self,
        *,
        recommendation_id: UUID,
        alert_id: UUID | None,
        action: str,
        previous_status: str,
        new_status: str,
        performed_by_user_id: UUID,
        assigned_to_user_id: UUID | None = None,
        comment: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        with get_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    """
                    UPDATE recommendations
                    SET status = %s
                    WHERE id = %s
                    RETURNING
                        id,
                        product_id,
                        forecast_id,
                        anomaly_id,
                        alert_id,
                        recommendation_type,
                        recommended_action,
                        rationale,
                        status,
                        generated_at,
                        expires_at,
                        created_at;
                    """,
                    (new_status, recommendation_id),
                )
                recommendation = cursor.fetchone()

                if not recommendation:
                    raise LookupError(f"Recommendation {recommendation_id} does not exist.")

                workflow_action = None
                if alert_id:
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

                details = {}
                if alert_id:
                    details["alert_id"] = str(alert_id)
                if workflow_action:
                    details["workflow_action_id"] = str(workflow_action["id"])

                audit_log = self._insert_workflow_audit_log(
                    cursor,
                    entity_type="recommendation",
                    entity_id=recommendation_id,
                    action=action,
                    previous_status=previous_status,
                    new_status=new_status,
                    performed_by_user_id=performed_by_user_id,
                    assigned_to_user_id=assigned_to_user_id,
                    comment=comment,
                    idempotency_key=idempotency_key,
                    details=details,
                )
                connection.commit()

        return {
            "recommendation": dict(recommendation),
            "workflow_action": dict(workflow_action) if workflow_action else None,
            "audit_log": dict(audit_log),
        }

    def _insert_workflow_audit_log(
        self,
        cursor,
        *,
        entity_type: str,
        entity_id: UUID,
        action: str,
        previous_status: str,
        new_status: str,
        performed_by_user_id: UUID,
        assigned_to_user_id: UUID | None,
        comment: str | None,
        idempotency_key: str | None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cursor.execute(
            """
            INSERT INTO workflow_audit_log (
                entity_type,
                entity_id,
                action_type,
                performed_by_user_id,
                assigned_to_user_id,
                previous_status,
                new_status,
                comment,
                idempotency_key,
                source,
                details,
                performed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'api', %s, now())
            RETURNING
                id,
                entity_type,
                entity_id,
                action_type,
                performed_by_user_id,
                assigned_to_user_id,
                previous_status,
                new_status,
                comment,
                idempotency_key,
                source,
                details,
                performed_at,
                created_at;
            """,
            (
                entity_type,
                entity_id,
                action,
                performed_by_user_id,
                assigned_to_user_id,
                previous_status,
                new_status,
                comment,
                idempotency_key,
                Jsonb(details or {}),
            ),
        )
        return cursor.fetchone()
