from __future__ import annotations

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
        )

        workflow_action = result["workflow_action"]
        return {
            "workflow_action": {
                "id": workflow_action["id"],
                "entity_type": "alert",
                "entity_id": workflow_action["alert_id"],
                "action": workflow_action["action_type"],
                "previous_status": workflow_action["previous_status"],
                "new_status": workflow_action["new_status"],
                "performed_by_user_id": workflow_action["performed_by_user_id"],
                "assigned_to_user_id": assigned_to_user_id,
                "comment": workflow_action["comment"],
                "performed_at": workflow_action["performed_at"],
                "idempotency_key": idempotency_key,
            },
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

        alert_id = recommendation.get("alert_id")
        if not alert_id:
            raise LookupError(
                "Recommendation workflow actions require an alert_id until the "
                "Sprint 10 audit log migration supports recommendation-native "
                "workflow records."
            )

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
            comment=comment,
        )

        workflow_action = result["workflow_action"]
        return {
            "workflow_action": {
                "id": workflow_action["id"],
                "entity_type": "recommendation",
                "entity_id": result["recommendation"]["id"],
                "action": workflow_action["action_type"],
                "previous_status": workflow_action["previous_status"],
                "new_status": workflow_action["new_status"],
                "performed_by_user_id": workflow_action["performed_by_user_id"],
                "assigned_to_user_id": assigned_to_user_id,
                "comment": workflow_action["comment"],
                "performed_at": workflow_action["performed_at"],
                "idempotency_key": idempotency_key,
            },
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
