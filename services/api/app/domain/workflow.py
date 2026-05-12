from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkflowTransitionError(ValueError):
    """Raised when a workflow status transition is not allowed."""


class WorkflowEntityType(str, Enum):
    alert = "alert"
    recommendation = "recommendation"


class WorkflowActionName(str, Enum):
    acknowledge = "acknowledge"
    assign = "assign"
    accept = "accept"
    reject = "reject"
    resolve = "resolve"
    dismiss = "dismiss"
    reopen = "reopen"
    comment = "comment"
    escalate = "escalate"


@dataclass(frozen=True)
class WorkflowTransition:
    entity_type: WorkflowEntityType
    action: WorkflowActionName
    previous_status: str
    new_status: str
    requires_comment: bool = False


ALERT_TRANSITIONS: frozenset[WorkflowTransition] = frozenset(
    {
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.acknowledge,
            "open",
            "acknowledged",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.assign,
            "open",
            "in_progress",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.assign,
            "acknowledged",
            "in_progress",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.assign,
            "in_progress",
            "in_progress",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.escalate,
            "open",
            "in_progress",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.escalate,
            "acknowledged",
            "in_progress",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.resolve,
            "acknowledged",
            "resolved",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.resolve,
            "in_progress",
            "resolved",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.dismiss,
            "open",
            "dismissed",
            requires_comment=True,
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.dismiss,
            "acknowledged",
            "dismissed",
            requires_comment=True,
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.dismiss,
            "in_progress",
            "dismissed",
            requires_comment=True,
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.reopen,
            "resolved",
            "open",
        ),
        WorkflowTransition(
            WorkflowEntityType.alert,
            WorkflowActionName.reopen,
            "dismissed",
            "open",
        ),
    },
)


RECOMMENDATION_TRANSITIONS: frozenset[WorkflowTransition] = frozenset(
    {
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.accept,
            "proposed",
            "accepted",
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.assign,
            "proposed",
            "proposed",
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.assign,
            "accepted",
            "accepted",
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.reject,
            "proposed",
            "rejected",
            requires_comment=True,
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.resolve,
            "accepted",
            "implemented",
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.dismiss,
            "proposed",
            "rejected",
            requires_comment=True,
        ),
        WorkflowTransition(
            WorkflowEntityType.recommendation,
            WorkflowActionName.reopen,
            "rejected",
            "proposed",
        ),
    },
)


WORKFLOW_TRANSITIONS: frozenset[WorkflowTransition] = ALERT_TRANSITIONS | RECOMMENDATION_TRANSITIONS

COMMENT_ACTIONS = frozenset({WorkflowActionName.comment})


def normalize_workflow_value(value: str | Enum) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def get_allowed_transitions(
    entity_type: WorkflowEntityType | str,
) -> frozenset[WorkflowTransition]:
    normalized_entity_type = WorkflowEntityType(normalize_workflow_value(entity_type))
    if normalized_entity_type == WorkflowEntityType.alert:
        return ALERT_TRANSITIONS
    if normalized_entity_type == WorkflowEntityType.recommendation:
        return RECOMMENDATION_TRANSITIONS
    return frozenset()


def validate_workflow_transition(
    *,
    entity_type: WorkflowEntityType | str,
    action: WorkflowActionName | str,
    previous_status: str | Enum,
    new_status: str | Enum,
    comment: str | None = None,
) -> WorkflowTransition | None:
    normalized_entity_type = WorkflowEntityType(normalize_workflow_value(entity_type))
    normalized_action = WorkflowActionName(normalize_workflow_value(action))
    normalized_previous_status = normalize_workflow_value(previous_status)
    normalized_new_status = normalize_workflow_value(new_status)

    if normalized_action in COMMENT_ACTIONS:
        if normalized_previous_status != normalized_new_status:
            msg = "Comment actions must not change workflow status."
            raise WorkflowTransitionError(msg)
        return None

    for transition in get_allowed_transitions(normalized_entity_type):
        if (
            transition.action == normalized_action
            and transition.previous_status == normalized_previous_status
            and transition.new_status == normalized_new_status
        ):
            if transition.requires_comment and not comment:
                msg = f"Comment is required for {normalized_action.value} actions."
                raise WorkflowTransitionError(
                    msg,
                )
            return transition

    msg = (
        "Workflow transition is not allowed: "
        f"{normalized_entity_type.value} {normalized_action.value} "
        f"{normalized_previous_status} -> {normalized_new_status}."
    )
    raise WorkflowTransitionError(
        msg,
    )


def is_workflow_transition_allowed(
    *,
    entity_type: WorkflowEntityType | str,
    action: WorkflowActionName | str,
    previous_status: str | Enum,
    new_status: str | Enum,
    comment: str | None = None,
) -> bool:
    try:
        validate_workflow_transition(
            entity_type=entity_type,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            comment=comment,
        )
    except (ValueError, WorkflowTransitionError):
        return False

    return True
