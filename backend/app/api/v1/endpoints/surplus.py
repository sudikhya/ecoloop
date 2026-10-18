from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.agents.recovery import extract_surplus_media, extract_surplus_text
from app.core.identity import Principal, current_principal
from app.domain.recovery_planning import list_household_proposals
from app.domain.surplus import (
    cancel_surplus,
    confirm_surplus,
    list_household_surplus,
    update_surplus,
)
from app.schemas.household import ApiResult, OpaqueId
from app.schemas.surplus import (
    CancelSurplusCommand,
    ConfirmSurplusCommand,
    SurplusIntakeTextCommand,
    UpdateSurplusCommand,
)

router = APIRouter(prefix="/surplus", tags=["Surplus demo"])


def _result(request_id: str, value: dict[str, Any]) -> ApiResult:
    return ApiResult(request_id=request_id, result=value)


@router.post("/intake/text", response_model=ApiResult)
async def intake_text(
    request: Request,
    command: SurplusIntakeTextCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    candidate = await extract_surplus_text(principal.uid, command.text)
    return _result(
        request.state.request_id, {"candidate": candidate, "persisted": False}
    )


@router.post("/intake/media", response_model=ApiResult)
async def intake_media(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    mime_type = request.headers.get("content-type", "")
    media = await request.body()
    candidate = await extract_surplus_media(principal.uid, media, mime_type)
    return _result(
        request.state.request_id, {"candidate": candidate, "persisted": False}
    )


@router.get("", response_model=ApiResult)
def read_surplus(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, list_household_surplus(principal))


@router.get("/route-proposals", response_model=ApiResult)
def read_route_proposals(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, list_household_proposals(principal))


@router.post("", response_model=ApiResult, status_code=status.HTTP_201_CREATED)
def create_surplus(
    request: Request,
    command: ConfirmSurplusCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, confirm_surplus(principal, command))


@router.patch("/{surplus_id}", response_model=ApiResult)
def edit_surplus(
    surplus_id: OpaqueId,
    request: Request,
    command: UpdateSurplusCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(
        request.state.request_id, update_surplus(principal, surplus_id, command)
    )


@router.post("/{surplus_id}/cancel", response_model=ApiResult)
def cancel(
    surplus_id: OpaqueId,
    request: Request,
    command: CancelSurplusCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(
        request.state.request_id, cancel_surplus(principal, surplus_id, command)
    )
