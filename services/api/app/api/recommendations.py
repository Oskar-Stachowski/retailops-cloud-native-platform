from uuid import UUID

from fastapi import APIRouter, Body, HTTPException, Query, status

from app.api.schemas import WorkflowMutationRequest, WorkflowMutationResponse
from app.auth.roles import get_demo_user
from app.domain.workflow import WorkflowActionName, WorkflowTransitionError
from app.services.workflow_service import WorkflowNotFoundError, WorkflowService


router = APIRouter(prefix="/recommendations", tags=["recommendations"])
workflow_service = WorkflowService()


def _apply_recommendation_action(
    *,
    recommendation_id: UUID,
    action: WorkflowActionName,
    request: WorkflowMutationRequest | None,
    user_id: str | None,
) -> dict:
    body = request or WorkflowMutationRequest()
    actor = get_demo_user(user_id)

    try:
        return workflow_service.apply_recommendation_action(
            recommendation_id=recommendation_id,
            action=action,
            actor=actor,
            assigned_to_user_id=body.assigned_to_user_id,
            comment=body.comment,
            idempotency_key=body.idempotency_key,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND) from exc
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
                "code": "workflow_target_not_available",
                "message": str(exc),
            },
        ) from exc


@router.post(
    "/{recommendation_id}/accept",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept a recommendation",
    description="Moves a proposed recommendation to accepted and records a workflow action.",
)
def accept_recommendation(
    recommendation_id: UUID,
    request: WorkflowMutationRequest | None = Body(default=None),
    user_id: str | None = Query(default=None, description="Local demo user id."),
):
    return _apply_recommendation_action(
        recommendation_id=recommendation_id,
        action=WorkflowActionName.accept,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{recommendation_id}/reject",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a recommendation",
    description="Rejects a proposed recommendation. A decision comment is required.",
)
def reject_recommendation(
    recommendation_id: UUID,
    request: WorkflowMutationRequest = Body(...),
    user_id: str | None = Query(default=None, description="Local demo user id."),
):
    return _apply_recommendation_action(
        recommendation_id=recommendation_id,
        action=WorkflowActionName.reject,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{recommendation_id}/assign",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign a recommendation",
    description="Assigns a recommendation owner without changing its status.",
)
def assign_recommendation(
    recommendation_id: UUID,
    request: WorkflowMutationRequest = Body(...),
    user_id: str | None = Query(default=None, description="Local demo user id."),
):
    if not request.assigned_to_user_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "assigned_to_user_id_required",
                "message": "assigned_to_user_id is required for assign actions.",
            },
        )

    return _apply_recommendation_action(
        recommendation_id=recommendation_id,
        action=WorkflowActionName.assign,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{recommendation_id}/resolve",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve a recommendation",
    description="Moves an accepted recommendation to implemented.",
)
def resolve_recommendation(
    recommendation_id: UUID,
    request: WorkflowMutationRequest | None = Body(default=None),
    user_id: str | None = Query(default=None, description="Local demo user id."),
):
    return _apply_recommendation_action(
        recommendation_id=recommendation_id,
        action=WorkflowActionName.resolve,
        request=request,
        user_id=user_id,
    )


@router.post(
    "/{recommendation_id}/dismiss",
    response_model=WorkflowMutationResponse,
    status_code=status.HTTP_200_OK,
    summary="Dismiss a recommendation",
    description="Dismisses a proposed recommendation. A decision comment is required.",
)
def dismiss_recommendation(
    recommendation_id: UUID,
    request: WorkflowMutationRequest = Body(...),
    user_id: str | None = Query(default=None, description="Local demo user id."),
):
    return _apply_recommendation_action(
        recommendation_id=recommendation_id,
        action=WorkflowActionName.dismiss,
        request=request,
        user_id=user_id,
    )
