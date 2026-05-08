from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas import (
    AlertWorkflowMutationRequest,
    RecommendationWorkflowMutationRequest,
    WorkflowActionCreateRequest,
    WorkflowActionResponse,
    WorkflowMutationResponse,
)


def test_alert_assign_request_requires_assignee():
    with pytest.raises(ValidationError):
        AlertWorkflowMutationRequest(action="assign")


def test_alert_dismiss_request_requires_comment():
    with pytest.raises(ValidationError):
        AlertWorkflowMutationRequest(action="dismiss")


def test_alert_request_rejects_recommendation_only_action():
    with pytest.raises(ValidationError):
        AlertWorkflowMutationRequest(
            action="accept",
            comment="Accepting this recommendation.",
        )


def test_recommendation_reject_request_requires_comment():
    with pytest.raises(ValidationError):
        RecommendationWorkflowMutationRequest(action="reject")


def test_recommendation_assign_request_accepts_assignee():
    assignee_id = uuid4()

    request = RecommendationWorkflowMutationRequest(
        action="assign",
        assigned_to_user_id=assignee_id,
        comment="Assigning to the category manager.",
    )

    assert request.assigned_to_user_id == assignee_id


def test_recommendation_request_rejects_alert_only_action():
    with pytest.raises(ValidationError):
        RecommendationWorkflowMutationRequest(
            action="acknowledge",
            comment="Acknowledging this item.",
        )


def test_generic_workflow_action_create_request_validates_transition():
    request = WorkflowActionCreateRequest(
        entity_type="alert",
        entity_id=uuid4(),
        action="acknowledge",
        previous_status="open",
        new_status="acknowledged",
    )

    assert request.entity_type == "alert"
    assert request.action == "acknowledge"


def test_generic_workflow_action_create_request_rejects_invalid_transition():
    with pytest.raises(ValidationError):
        WorkflowActionCreateRequest(
            entity_type="alert",
            entity_id=uuid4(),
            action="assign",
            previous_status="resolved",
            new_status="in_progress",
        )


def test_generic_recommendation_assign_keeps_status_and_requires_assignee():
    assignee_id = uuid4()

    request = WorkflowActionCreateRequest(
        entity_type="recommendation",
        entity_id=uuid4(),
        action="assign",
        previous_status="proposed",
        new_status="proposed",
        assigned_to_user_id=assignee_id,
    )

    assert request.assigned_to_user_id == assignee_id


def test_workflow_mutation_response_shape_is_strict():
    response = WorkflowMutationResponse(
        workflow_action=WorkflowActionResponse(
            id=uuid4(),
            entity_type="alert",
            entity_id=uuid4(),
            action="acknowledge",
            previous_status="open",
            new_status="acknowledged",
            performed_by_user_id=uuid4(),
            performed_at=datetime.now(timezone.utc),
        ),
        status="acknowledged",
        message="Workflow action recorded.",
    )

    assert response.workflow_action.action == "acknowledge"

    with pytest.raises(ValidationError):
        WorkflowMutationResponse(
            workflow_action=response.workflow_action,
            status="acknowledged",
            message="Workflow action recorded.",
            unexpected="not allowed",
        )
