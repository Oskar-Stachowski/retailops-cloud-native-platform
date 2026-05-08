from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.auth.roles import DEMO_USERS
from app.domain.workflow import WorkflowTransitionError
from app.services.workflow_service import WorkflowNotFoundError, WorkflowService


class FakeWorkflowRepository:
    def __init__(self, alert=None):
        self.alert = alert
        self.applied_action = None
        self.actor_user_id = uuid4()

    def get_alert(self, alert_id):
        return self.alert

    def resolve_demo_actor_user_id(self, user):
        return self.actor_user_id

    def apply_alert_workflow_action(self, **kwargs):
        self.applied_action = kwargs
        return {
            "alert": {
                "id": kwargs["alert_id"],
                "status": kwargs["new_status"],
            },
            "workflow_action": {
                "id": uuid4(),
                "alert_id": kwargs["alert_id"],
                "performed_by_user_id": kwargs["performed_by_user_id"],
                "action_type": kwargs["action"],
                "comment": kwargs["comment"],
                "previous_status": kwargs["previous_status"],
                "new_status": kwargs["new_status"],
                "performed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
            },
        }


def make_alert(status="open"):
    return {
        "id": uuid4(),
        "status": status,
    }


def test_apply_alert_acknowledge_records_status_transition():
    alert = make_alert(status="open")
    repository = FakeWorkflowRepository(alert=alert)
    service = WorkflowService(repository=repository)

    result = service.apply_alert_action(
        alert_id=alert["id"],
        action="acknowledge",
        actor=DEMO_USERS["platform-admin"],
    )

    assert result["status"] == "acknowledged"
    assert result["workflow_action"]["entity_type"] == "alert"
    assert repository.applied_action["previous_status"] == "open"
    assert repository.applied_action["new_status"] == "acknowledged"


def test_apply_alert_assign_moves_open_alert_to_in_progress():
    alert = make_alert(status="open")
    assignee_id = uuid4()
    repository = FakeWorkflowRepository(alert=alert)
    service = WorkflowService(repository=repository)

    result = service.apply_alert_action(
        alert_id=alert["id"],
        action="assign",
        actor=DEMO_USERS["platform-admin"],
        assigned_to_user_id=assignee_id,
        comment="Assigning to inventory planning.",
    )

    assert result["status"] == "in_progress"
    assert result["workflow_action"]["assigned_to_user_id"] == assignee_id
    assert repository.applied_action["assigned_to_user_id"] == assignee_id


def test_apply_alert_resolve_rejects_open_alert():
    alert = make_alert(status="open")
    service = WorkflowService(repository=FakeWorkflowRepository(alert=alert))

    with pytest.raises(WorkflowTransitionError):
        service.apply_alert_action(
            alert_id=alert["id"],
            action="resolve",
            actor=DEMO_USERS["platform-admin"],
        )


def test_apply_alert_dismiss_requires_comment():
    alert = make_alert(status="acknowledged")
    service = WorkflowService(repository=FakeWorkflowRepository(alert=alert))

    with pytest.raises(WorkflowTransitionError):
        service.apply_alert_action(
            alert_id=alert["id"],
            action="dismiss",
            actor=DEMO_USERS["platform-admin"],
        )


def test_apply_alert_comment_keeps_existing_status():
    alert = make_alert(status="in_progress")
    repository = FakeWorkflowRepository(alert=alert)
    service = WorkflowService(repository=repository)

    result = service.apply_alert_action(
        alert_id=alert["id"],
        action="comment",
        actor=DEMO_USERS["platform-admin"],
        comment="Inventory owner is checking supplier lead time.",
    )

    assert result["status"] == "in_progress"
    assert repository.applied_action["previous_status"] == "in_progress"
    assert repository.applied_action["new_status"] == "in_progress"


def test_apply_alert_action_raises_not_found_for_missing_alert():
    service = WorkflowService(repository=FakeWorkflowRepository(alert=None))

    with pytest.raises(WorkflowNotFoundError):
        service.apply_alert_action(
            alert_id=uuid4(),
            action="acknowledge",
            actor=DEMO_USERS["platform-admin"],
        )
