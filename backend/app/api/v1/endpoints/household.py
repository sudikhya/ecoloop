from typing import Any

from fastapi import APIRouter, Depends, Request, status

from app.core.errors import DomainError
from app.core.firestore import get_firestore
from app.core.identity import Principal, authenticated_uid, current_principal
from app.agents.household import generate_household_turn
from app.domain.household_creation import create_household, delete_household
from app.domain.repository import confirm_facts, list_shopping_entries, record_outcome, save_shopping_entry
from app.schemas.household import (
    ApiResult,
    AssistantEnvelope,
    AssistantTurnRequest,
    ConfirmFactsCommand,
    CreateHouseholdCommand,
    RecordOutcomeCommand,
    ShoppingCommand,
)


router = APIRouter()


def _result(request_id: str, value: dict[str, Any]) -> ApiResult:
    return ApiResult(request_id=request_id, result=value)


@router.post("/households", response_model=ApiResult, status_code=status.HTTP_201_CREATED)
def household_create(
    request: Request,
    command: CreateHouseholdCommand,
    uid: str = Depends(authenticated_uid),
) -> ApiResult:
    return _result(request.state.request_id, create_household(uid, command))


@router.delete("/households/{household_id}", response_model=ApiResult)
def household_delete(
    request: Request,
    household_id: str,
    uid: str = Depends(authenticated_uid),
) -> ApiResult:
    return _result(request.state.request_id, delete_household(uid, household_id))



@router.get("/kitchen", response_model=ApiResult)
def get_kitchen(
    request: Request,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    # Request ID is injected by middleware at the API edge, not accepted from the client.
    try:
        query = (
            get_firestore()
            .collection("households")
            .document(principal.household_id)
            .collection("food_observations")
            .order_by("observed_at", direction="DESCENDING")
            .limit(200)
        )
        items = [snapshot.to_dict() | {"item_id": snapshot.id} for snapshot in query.stream()]
    except Exception as exc:
        raise DomainError("DATA_UNAVAILABLE", "The kitchen is unavailable.", 503, True) from exc
    return _result(request.state.request_id, {"observations": items})


@router.post("/facts/confirm", response_model=ApiResult)
def confirm(
    request: Request,
    command: ConfirmFactsCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, confirm_facts(principal, command))


@router.post("/outcomes", response_model=ApiResult)
def outcome(
    request: Request,
    command: RecordOutcomeCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, record_outcome(principal, command))


@router.get("/shopping", response_model=ApiResult)
def read_shopping(request: Request, principal: Principal = Depends(current_principal)) -> ApiResult:
    return _result(request.state.request_id, {"entries": list_shopping_entries(principal)})


@router.post("/shopping", response_model=ApiResult)
def shopping(
    request: Request,
    command: ShoppingCommand,
    principal: Principal = Depends(current_principal),
) -> ApiResult:
    return _result(request.state.request_id, save_shopping_entry(principal, command))


@router.post("/assistant/turns", response_model=AssistantEnvelope)
async def assistant_turn(
    request: Request,
    command: AssistantTurnRequest,
    principal: Principal = Depends(current_principal),
) -> AssistantEnvelope:
    return await generate_household_turn(principal, command, request.state.request_id)
