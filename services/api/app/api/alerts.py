from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.api.schemas import WorkflowMutationRequest, WorkflowMutationResponse
from app.auth.roles import PERMISSION_WORKFLOW_WRITE, get_demo_user, require_permission
from app.domain.workflow import WorkflowActionName, WorkflowTransitionError
from app.services.workflow_service import WorkflowNotFoundError, WorkflowService

router = APIRouter(prefix="/alerts", tags=["alerts"])
workflow_service = WorkflowService()
OptionalWorkflowBody = Annotated[WorkflowMutationRequest | None, Body()]
RequiredWorkflowBody = Annotated[WorkflowMutationRequest, Body()]
DemoUserQuery = Annotated[str | None, Query(description="Local demo user id.")]


def _apply_alert_action(
    *,
    alert_id: UUID,
    action: WorkflowActionName,
    request: WorkflowMutationRequest | None,
    user_id: str | None,
) -> dict:
    body = request or WorkflowMutationRequest()
    actor = get_demo_user(user_id)
    require_permission(actor, PERMISSION_WORKFLOW_WRITE)

    try:
        return workflow_service.apply_alert_action(
            alert_id=alert_id,
            action=action,
            actor=actor,
            assigned_to_user_id=body.assigned_to_user_id,
            comment=body.comment,
            idempotency_key=body.idempotency_key,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        ) from exc
    except WorkflowTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "workflow_transition_not_allowed",
                "message": str(exc),
            },
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "workflow_actor_not_available",
                "message": str(exc),
            },
        ) from exc


@router.post(
    "/{alert_id}/acknowledge",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Acknowledge an alert",
    description="Moves an open alert to acknowledged and records a workflow action.",
)
def acknowledge_alert(
    alert_id: UUID,
    request: OptionalWorkflowBody = None,
    user_id: DemoUserQuery = None,
) -> dict[str, object]:
    return _apply_alert_action(
        alert_id=alert_id,
        action=WorkflowActionName.acknowledge,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{alert_id}/assign",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign an alert",
    description="Assigns an alert, moves it to in_progress and records a workflow action.",
)
def assign_alert(
    alert_id: UUID,
    request: RequiredWorkflowBody,
    user_id: DemoUserQuery = None,
) -> dict[str, object]:
    if not request.assigned_to_user_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "assigned_to_user_id_required",
                "message": "assigned_to_user_id is required for assign actions.",
            },
        )

    return _apply_alert_action(
        alert_id=alert_id,
        action=WorkflowActionName.assign,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{alert_id}/resolve",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve an alert",
    description="Moves an acknowledged or in-progress alert to resolved.",
)
def resolve_alert(
    alert_id: UUID,
    request: OptionalWorkflowBody = None,
    user_id: DemoUserQuery = None,
) -> dict[str, object]:
    return _apply_alert_action(
        alert_id=alert_id,
        action=WorkflowActionName.resolve,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{alert_id}/dismiss",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Dismiss an alert",
    description="Dismisses an alert. A decision comment is required.",
)
def dismiss_alert(
    alert_id: UUID,
    request: RequiredWorkflowBody,
    user_id: DemoUserQuery = None,
) -> dict[str, object]:
    return _apply_alert_action(
        alert_id=alert_id,
        action=WorkflowActionName.dismiss,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{alert_id}/comment",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Comment on an alert",
    description="Records a comment without changing the current alert status.",
)
def comment_on_alert(
    alert_id: UUID,
    request: RequiredWorkflowBody,
    user_id: DemoUserQuery = None,
) -> dict[str, object]:
    return _apply_alert_action(
        alert_id=alert_id,
        action=WorkflowActionName.comment,
        request=request,
        user_id=user_id,
    )
