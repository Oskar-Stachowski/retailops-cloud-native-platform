from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.auth.roles import DEMO_USERS
from app.domain.workflow import WorkflowTransitionError
from app.services.workflow_service import WorkflowNotFoundError, WorkflowService


class FakeWorkflowRepository:
    def __init__(self, alert=None, recommendation=None, existing_audit_log=None):
        self.alert = alert
        self.recommendation = recommendation
        self.existing_audit_log = existing_audit_log
        self.applied_action = None
        self.actor_user_id = uuid4()

    def get_alert(self, alert_id):
        return self.alert

    def get_recommendation(self, recommendation_id):
        return self.recommendation

    def resolve_demo_actor_user_id(self, user):
        return self.actor_user_id

    def get_workflow_audit_log(self, **kwargs):
        return self.existing_audit_log

    def apply_alert_workflow_action(self, **kwargs):
        self.applied_action = kwargs
        audit_log_id = uuid4()
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
            "audit_log": {
                "id": audit_log_id,
                "entity_type": "alert",
                "entity_id": kwargs["alert_id"],
                "performed_by_user_id": kwargs["performed_by_user_id"],
                "assigned_to_user_id": kwargs["assigned_to_user_id"],
                "action_type": kwargs["action"],
                "comment": kwargs["comment"],
                "previous_status": kwargs["previous_status"],
                "new_status": kwargs["new_status"],
                "performed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
            },
        }

    def apply_recommendation_workflow_action(self, **kwargs):
        self.applied_action = kwargs
        audit_log = {
            "id": uuid4(),
            "entity_type": "recommendation",
            "entity_id": kwargs["recommendation_id"],
            "performed_by_user_id": kwargs["performed_by_user_id"],
            "assigned_to_user_id": kwargs["assigned_to_user_id"],
            "action_type": kwargs["action"],
            "comment": kwargs["comment"],
            "previous_status": kwargs["previous_status"],
            "new_status": kwargs["new_status"],
            "performed_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
        }
        workflow_action = None
        if kwargs["alert_id"]:
            workflow_action = {
                "id": uuid4(),
                "alert_id": kwargs["alert_id"],
                "performed_by_user_id": kwargs["performed_by_user_id"],
                "action_type": kwargs["action"],
                "comment": kwargs["comment"],
                "previous_status": kwargs["previous_status"],
                "new_status": kwargs["new_status"],
                "performed_at": datetime.now(timezone.utc),
                "created_at": datetime.now(timezone.utc),
            }

        return {
            "recommendation": {
                "id": kwargs["recommendation_id"],
                "status": kwargs["new_status"],
            },
            "workflow_action": workflow_action,
            "audit_log": audit_log,
        }


def make_alert(status="open"):
    return {
        "id": uuid4(),
        "status": status,
    }


def make_recommendation(status="proposed", alert_id=None):
    return {
        "id": uuid4(),
        "alert_id": uuid4() if alert_id is None else alert_id,
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


def test_apply_alert_action_replays_existing_idempotent_result():
    alert = make_alert(status="acknowledged")
    audit_log = {
        "id": uuid4(),
        "entity_type": "alert",
        "entity_id": alert["id"],
        "performed_by_user_id": uuid4(),
        "assigned_to_user_id": None,
        "action_type": "acknowledge",
        "comment": None,
        "previous_status": "open",
        "new_status": "acknowledged",
        "idempotency_key": "ack-alert-001",
        "details": {"workflow_action_id": str(uuid4())},
        "performed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    repository = FakeWorkflowRepository(alert=alert, existing_audit_log=audit_log)
    service = WorkflowService(repository=repository)

    result = service.apply_alert_action(
        alert_id=alert["id"],
        action="acknowledge",
        actor=DEMO_USERS["platform-admin"],
        idempotency_key="ack-alert-001",
    )

    assert result["status"] == "acknowledged"
    assert result["workflow_action"]["audit_log_id"] == audit_log["id"]
    assert result["workflow_action"]["idempotency_key"] == "ack-alert-001"
    assert repository.applied_action is None


def test_apply_alert_action_rejects_idempotency_key_reused_for_different_action():
    alert = make_alert(status="acknowledged")
    audit_log = {
        "id": uuid4(),
        "entity_type": "alert",
        "entity_id": alert["id"],
        "performed_by_user_id": uuid4(),
        "assigned_to_user_id": None,
        "action_type": "acknowledge",
        "comment": None,
        "previous_status": "open",
        "new_status": "acknowledged",
        "idempotency_key": "workflow-key-001",
        "details": {},
        "performed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    service = WorkflowService(
        repository=FakeWorkflowRepository(alert=alert, existing_audit_log=audit_log)
    )

    with pytest.raises(WorkflowTransitionError):
        service.apply_alert_action(
            alert_id=alert["id"],
            action="resolve",
            actor=DEMO_USERS["platform-admin"],
            idempotency_key="workflow-key-001",
        )


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


def test_apply_recommendation_accept_records_decision():
    recommendation = make_recommendation(status="proposed")
    repository = FakeWorkflowRepository(recommendation=recommendation)
    service = WorkflowService(repository=repository)

    result = service.apply_recommendation_action(
        recommendation_id=recommendation["id"],
        action="accept",
        actor=DEMO_USERS["platform-admin"],
    )

    assert result["status"] == "accepted"
    assert result["workflow_action"]["entity_type"] == "recommendation"
    assert repository.applied_action["previous_status"] == "proposed"
    assert repository.applied_action["new_status"] == "accepted"


def test_apply_recommendation_action_replays_existing_idempotent_result():
    recommendation = make_recommendation(status="accepted")
    audit_log = {
        "id": uuid4(),
        "entity_type": "recommendation",
        "entity_id": recommendation["id"],
        "performed_by_user_id": uuid4(),
        "assigned_to_user_id": None,
        "action_type": "accept",
        "comment": None,
        "previous_status": "proposed",
        "new_status": "accepted",
        "idempotency_key": "accept-rec-001",
        "details": {},
        "performed_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    }
    repository = FakeWorkflowRepository(
        recommendation=recommendation,
        existing_audit_log=audit_log,
    )
    service = WorkflowService(repository=repository)

    result = service.apply_recommendation_action(
        recommendation_id=recommendation["id"],
        action="accept",
        actor=DEMO_USERS["platform-admin"],
        idempotency_key="accept-rec-001",
    )

    assert result["status"] == "accepted"
    assert result["workflow_action"]["id"] == audit_log["id"]
    assert result["workflow_action"]["audit_log_id"] == audit_log["id"]
    assert repository.applied_action is None


def test_apply_recommendation_reject_requires_comment():
    recommendation = make_recommendation(status="proposed")
    service = WorkflowService(
        repository=FakeWorkflowRepository(recommendation=recommendation)
    )

    with pytest.raises(WorkflowTransitionError):
        service.apply_recommendation_action(
            recommendation_id=recommendation["id"],
            action="reject",
            actor=DEMO_USERS["platform-admin"],
        )


def test_apply_recommendation_resolve_requires_accepted_status():
    recommendation = make_recommendation(status="proposed")
    service = WorkflowService(
        repository=FakeWorkflowRepository(recommendation=recommendation)
    )

    with pytest.raises(WorkflowTransitionError):
        service.apply_recommendation_action(
            recommendation_id=recommendation["id"],
            action="resolve",
            actor=DEMO_USERS["platform-admin"],
        )


def test_apply_recommendation_action_records_native_audit_without_alert_link():
    recommendation = make_recommendation(status="proposed", alert_id=None)
    recommendation["alert_id"] = None
    repository = FakeWorkflowRepository(recommendation=recommendation)
    service = WorkflowService(repository=repository)

    result = service.apply_recommendation_action(
        recommendation_id=recommendation["id"],
        action="accept",
        actor=DEMO_USERS["platform-admin"],
    )

    assert result["status"] == "accepted"
    assert result["workflow_action"]["entity_type"] == "recommendation"
    assert result["workflow_action"]["id"] == result["workflow_action"]["audit_log_id"]
    assert repository.applied_action["alert_id"] is None
