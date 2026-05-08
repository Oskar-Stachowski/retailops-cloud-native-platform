from __future__ import annotations

from typing import Any
from uuid import UUID

from app.auth.roles import DemoUser
from app.domain.workflow import (
    WorkflowActionName,
    WorkflowEntityType,
    WorkflowTransitionError,
    validate_workflow_transition,
)
from app.repositories.workflow_repository import WorkflowRepository


class WorkflowNotFoundError(LookupError):
    """Raised when a workflow target cannot be found."""


class WorkflowService:
    """Application service for operational workflow mutations."""

    def __init__(self, repository: WorkflowRepository | None = None) -> None:
        self.repository = repository or WorkflowRepository()

    def apply_alert_action(
        self,
        *,
        alert_id: UUID,
        action: WorkflowActionName | str,
        actor: DemoUser,
        assigned_to_user_id: UUID | None = None,
        comment: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        normalized_action = WorkflowActionName(action)
        alert = self.repository.get_alert(alert_id)

        if not alert:
            raise WorkflowNotFoundError(f"Alert {alert_id} does not exist.")

        if idempotency_key:
            existing_action = self.repository.get_workflow_audit_log(
                entity_type="alert",
                entity_id=alert_id,
                idempotency_key=idempotency_key,
            )
            if existing_action:
                return self._workflow_response_from_audit(
                    entity_type="alert",
                    entity_id=alert_id,
                    audit_log=existing_action,
                    expected_action=normalized_action,
                    message="Alert workflow action recorded.",
                )

        previous_status = str(alert["status"])
        new_status = self._next_alert_status(
            action=normalized_action,
            previous_status=previous_status,
        )

        try:
            validate_workflow_transition(
                entity_type=WorkflowEntityType.alert,
                action=normalized_action,
                previous_status=previous_status,
                new_status=new_status,
                comment=comment,
            )
        except WorkflowTransitionError:
            raise

        actor_user_id = self.repository.resolve_demo_actor_user_id(actor)
        result = self.repository.apply_alert_workflow_action(
            alert_id=alert_id,
            action=normalized_action.value,
            previous_status=previous_status,
            new_status=new_status,
            performed_by_user_id=actor_user_id,
            assigned_to_user_id=assigned_to_user_id,
            comment=comment,
            idempotency_key=idempotency_key,
        )

        workflow_action = result["workflow_action"]
        audit_log = result["audit_log"]
        return {
            "workflow_action": self._workflow_action_response(
                entity_type="alert",
                entity_id=workflow_action["alert_id"],
                action_record=workflow_action,
                audit_log=audit_log,
            ),
            "status": result["alert"]["status"],
            "message": "Alert workflow action recorded.",
        }

    def apply_recommendation_action(
        self,
        *,
        recommendation_id: UUID,
        action: WorkflowActionName | str,
        actor: DemoUser,
        assigned_to_user_id: UUID | None = None,
        comment: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        normalized_action = WorkflowActionName(action)
        recommendation = self.repository.get_recommendation(recommendation_id)

        if not recommendation:
            raise WorkflowNotFoundError(
                f"Recommendation {recommendation_id} does not exist."
            )

        if idempotency_key:
            existing_action = self.repository.get_workflow_audit_log(
                entity_type="recommendation",
                entity_id=recommendation_id,
                idempotency_key=idempotency_key,
            )
            if existing_action:
                return self._workflow_response_from_audit(
                    entity_type="recommendation",
                    entity_id=recommendation_id,
                    audit_log=existing_action,
                    expected_action=normalized_action,
                    message="Recommendation workflow action recorded.",
                )

        alert_id = recommendation.get("alert_id")
        previous_status = str(recommendation["status"])
        new_status = self._next_recommendation_status(
            action=normalized_action,
            previous_status=previous_status,
        )

        validate_workflow_transition(
            entity_type=WorkflowEntityType.recommendation,
            action=normalized_action,
            previous_status=previous_status,
            new_status=new_status,
            comment=comment,
        )

        actor_user_id = self.repository.resolve_demo_actor_user_id(actor)
        result = self.repository.apply_recommendation_workflow_action(
            recommendation_id=recommendation_id,
            alert_id=alert_id,
            action=normalized_action.value,
            previous_status=previous_status,
            new_status=new_status,
            performed_by_user_id=actor_user_id,
            assigned_to_user_id=assigned_to_user_id,
            comment=comment,
            idempotency_key=idempotency_key,
        )

        audit_log = result["audit_log"]
        workflow_action = result["workflow_action"] or audit_log
        return {
            "workflow_action": self._workflow_action_response(
                entity_type="recommendation",
                entity_id=result["recommendation"]["id"],
                action_record=workflow_action,
                audit_log=audit_log,
            ),
            "status": result["recommendation"]["status"],
            "message": "Recommendation workflow action recorded.",
        }

    def _next_alert_status(
        self,
        *,
        action: WorkflowActionName,
        previous_status: str,
    ) -> str:
        if action == WorkflowActionName.acknowledge:
            return "acknowledged"
        if action == WorkflowActionName.assign:
            if previous_status == "in_progress":
                return previous_status
            return "in_progress"
        if action == WorkflowActionName.resolve:
            return "resolved"
        if action == WorkflowActionName.dismiss:
            return "dismissed"
        if action == WorkflowActionName.comment:
            return previous_status

        raise WorkflowTransitionError(f"{action.value} is not supported for alerts.")

    def _next_recommendation_status(
        self,
        *,
        action: WorkflowActionName,
        previous_status: str,
    ) -> str:
        if action == WorkflowActionName.accept:
            return "accepted"
        if action == WorkflowActionName.reject:
            return "rejected"
        if action == WorkflowActionName.assign:
            return previous_status
        if action == WorkflowActionName.resolve:
            return "implemented"
        if action == WorkflowActionName.dismiss:
            return "rejected"
        if action == WorkflowActionName.comment:
            return previous_status

        raise WorkflowTransitionError(
            f"{action.value} is not supported for recommendations."
        )

    def _workflow_response_from_audit(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        audit_log: dict[str, Any],
        expected_action: WorkflowActionName,
        message: str,
    ) -> dict:
        if audit_log["action_type"] != expected_action.value:
            raise WorkflowTransitionError(
                "Idempotency key is already used for a different workflow action."
            )

        return {
            "workflow_action": self._workflow_action_response(
                entity_type=entity_type,
                entity_id=entity_id,
                action_record=audit_log,
                audit_log=audit_log,
            ),
            "status": audit_log["new_status"],
            "message": message,
        }

    def _workflow_action_response(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        action_record: dict[str, Any],
        audit_log: dict[str, Any],
    ) -> dict[str, Any]:
        action_id = action_record["id"]
        if action_record["id"] == audit_log["id"]:
            details = audit_log.get("details") or {}
            workflow_action_id = details.get("workflow_action_id")
            if workflow_action_id:
                action_id = UUID(str(workflow_action_id))

        return {
            "id": action_id,
            "audit_log_id": audit_log["id"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "action": action_record["action_type"],
            "previous_status": action_record["previous_status"],
            "new_status": action_record["new_status"],
            "performed_by_user_id": action_record["performed_by_user_id"],
            "assigned_to_user_id": audit_log.get("assigned_to_user_id"),
            "comment": action_record["comment"],
            "performed_at": action_record["performed_at"],
            "idempotency_key": audit_log.get("idempotency_key"),
        }
