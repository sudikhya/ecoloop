from fastapi import APIRouter, Depends, Request

from app.agents.memory_bank import memory_bank_status, sync_approved_preference
from app.core.errors import DomainError
from app.core.identity import household_uid
from app.domain.preferences import (
    change_preference,
    get_preference_record,
    list_preferences,
    list_preferences_needing_memory_sync,
)
from app.schemas.household import ApiResult
from app.schemas.preferences import (
    DeletePreferenceCommand,
    PreferenceCommand,
    PreferenceId,
    PreferenceMemorySyncCommand,
)

router = APIRouter()


@router.get("/preferences", response_model=ApiResult)
def read_preferences(request: Request, uid: str = Depends(household_uid)) -> ApiResult:
    pending_cleanup = [
        item
        for item in list_preferences_needing_memory_sync(uid, limit=50)
        if item["status"] == "REVOKED" and item["memory_bank_cleanup_required"]
    ]
    return ApiResult(
        request_id=request.state.request_id,
        result={
            "preferences": list_preferences(uid),
            "memory_bank_cleanup_pending": pending_cleanup,
            "memory_bank": memory_bank_status(),
        },
    )


@router.put("/preferences/{preference_id}", response_model=ApiResult)
def save_preference(request: Request, preference_id: PreferenceId, command: PreferenceCommand, uid: str = Depends(household_uid)) -> ApiResult:
    result = change_preference(uid, preference_id, command, delete=False)
    sync_status = sync_approved_preference(uid, preference_id)
    result["memory_bank_sync"] = {"status": sync_status, "version": result["version"]}
    return ApiResult(request_id=request.state.request_id, result=result)


@router.delete("/preferences/{preference_id}", response_model=ApiResult)
def remove_preference(request: Request, preference_id: PreferenceId, command: DeletePreferenceCommand, uid: str = Depends(household_uid)) -> ApiResult:
    result = change_preference(uid, preference_id, command, delete=True)
    sync_status = sync_approved_preference(uid, preference_id)
    result["memory_bank_sync"] = {"status": sync_status, "version": result["version"]}
    return ApiResult(request_id=request.state.request_id, result=result)


@router.post("/preferences/{preference_id}/memory-sync", response_model=ApiResult)
def retry_preference_memory_sync(request: Request, preference_id: PreferenceId, command: PreferenceMemorySyncCommand, uid: str = Depends(household_uid)) -> ApiResult:
    """Retry synchronization of one owner-scoped, consented preference."""
    if get_preference_record(uid, preference_id) is None:
        raise DomainError("PREFERENCE_NOT_FOUND", "Preference data is unavailable.", 404)
    sync_status = sync_approved_preference(uid, preference_id)
    result = get_preference_record(uid, preference_id)
    if result is None:
        raise DomainError("DATA_UNAVAILABLE", "Preference data is unavailable.", 404)
    result["memory_bank_sync"] = {"status": sync_status, "version": result["version"]}
    return ApiResult(request_id=request.state.request_id, result=result)
