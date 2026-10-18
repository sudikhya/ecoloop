from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.core.identity import NgoPrincipal, current_ngo
from app.domain.recovery_planning import list_ngo_proposals, plan_ngo_request
from app.domain.surplus import (
    create_ngo_request,
    list_central_surplus,
    require_surplus_pilot,
)
from app.schemas.household import ApiResult, OpaqueId
from app.schemas.surplus import NgoRequestCommand, PlanNgoRequestCommand

router = APIRouter(prefix="/ngo", tags=["NGO demo"])


def _result(request_id: str, value: dict[str, Any]) -> ApiResult:
    return ApiResult(request_id=request_id, result=value)


@router.get("/me", response_model=ApiResult)
def read_ngo_account(
    request: Request,
    principal: NgoPrincipal = Depends(current_ngo),
) -> ApiResult:
    require_surplus_pilot()
    return _result(
        request.state.request_id,
        {
            "uid": principal.uid,
            "ngo_id": principal.ngo_id,
            "role": principal.role,
            "demo_only": True,
        },
    )


@router.get("/surplus", response_model=ApiResult)
def read_central_surplus(
    request: Request,
    principal: NgoPrincipal = Depends(current_ngo),
) -> ApiResult:
    return _result(request.state.request_id, list_central_surplus(principal))


@router.post("/requests", response_model=ApiResult, status_code=status.HTTP_201_CREATED)
def create_request(
    request: Request,
    command: NgoRequestCommand,
    principal: NgoPrincipal = Depends(current_ngo),
) -> ApiResult:
    return _result(request.state.request_id, create_ngo_request(principal, command))


@router.post(
    "/requests/{request_id}/plan",
    response_model=ApiResult,
    status_code=status.HTTP_201_CREATED,
)
async def plan_request(
    request_id: OpaqueId,
    request: Request,
    command: PlanNgoRequestCommand,
    principal: NgoPrincipal = Depends(current_ngo),
) -> ApiResult:
    return _result(
        request.state.request_id, await plan_ngo_request(principal, request_id, command)
    )


@router.get("/proposals", response_model=ApiResult)
def read_proposals(
    request: Request,
    principal: NgoPrincipal = Depends(current_ngo),
) -> ApiResult:
    return _result(request.state.request_id, list_ngo_proposals(principal))
