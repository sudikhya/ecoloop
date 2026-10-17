from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from firebase_admin import firestore

from app.core.errors import DomainError
from app.core.firestore import get_firestore
from app.schemas.household import CreateHouseholdCommand

MAX_HOUSEHOLD_CREATIONS_PER_UTC_DAY = 5


def _payload_hash(command: CreateHouseholdCommand) -> str:
    canonical = json.dumps(command.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _request_ref(db: Any, uid: str, idempotency_key: str) -> Any:
    actor_scope = _actor_scope(uid)
    key_scope = hashlib.sha256(idempotency_key.encode("utf-8")).hexdigest()
    return db.collection("users").document(actor_scope).collection("household_creation_requests").document(key_scope)


def _actor_scope(uid: str) -> str:
    return hashlib.sha256(uid.encode("utf-8")).hexdigest()


def _validate_retry_result(
    transaction: Any,
    db: Any,
    uid: str,
    snapshot: Any,
    payload_hash: str,
) -> dict[str, str]:
    previous = snapshot.to_dict() or {}
    if previous.get("actor_uid") != uid or previous.get("payload_hash") != payload_hash:
        raise DomainError("IDEMPOTENCY_CONFLICT", "This request key was already used for a different command.", 409)
    result = previous.get("result")
    if not isinstance(result, dict):
        raise DomainError("DATA_UNAVAILABLE", "The saved household result is unavailable.", 503, True)
    household_id = result.get("household_id")
    name = result.get("name")
    if (
        not isinstance(household_id, str)
        or not household_id
        or not isinstance(name, str)
        or result.get("role") != "OWNER"
    ):
        raise DomainError("DATA_UNAVAILABLE", "The saved household result is invalid.", 503, True)

    household_ref = db.collection("households").document(household_id)
    member_ref = household_ref.collection("members").document(uid)
    household_snapshot = household_ref.get(transaction=transaction)
    member_snapshot = member_ref.get(transaction=transaction)
    household = household_snapshot.to_dict() if household_snapshot.exists else None
    member = member_snapshot.to_dict() if member_snapshot.exists else None
    if (
        not household
        or household.get("name") != name
        or not member
        or member.get("uid") != uid
        or member.get("role") != "OWNER"
        or member.get("status") != "ACTIVE"
    ):
        raise DomainError("DATA_UNAVAILABLE", "The saved household could not be verified.", 503, True)
    return {"household_id": household_id, "name": name, "role": "OWNER"}


def create_household(uid: str, command: CreateHouseholdCommand) -> dict[str, str]:
    db = get_firestore()
    request_ref = _request_ref(db, uid, command.idempotency_key)
    payload_hash = _payload_hash(command)
    household_id = uuid4().hex
    household_ref = db.collection("households").document(household_id)
    member_ref = household_ref.collection("members").document(uid)
    created_at = datetime.now(timezone.utc)
    utc_day = created_at.date().isoformat()
    quota_ref = (
        db.collection("users")
        .document(_actor_scope(uid))
        .collection("household_creation_quotas")
        .document(utc_day)
    )
    result = {"household_id": household_id, "name": command.name, "role": "OWNER"}

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, str]:
        request_snapshot = request_ref.get(transaction=transaction)
        if request_snapshot.exists:
            return _validate_retry_result(transaction, db, uid, request_snapshot, payload_hash)

        quota_snapshot = quota_ref.get(transaction=transaction)
        household_snapshot = household_ref.get(transaction=transaction)
        member_snapshot = member_ref.get(transaction=transaction)
        if household_snapshot.exists or member_snapshot.exists:
            raise DomainError("IDEMPOTENCY_CONFLICT", "This request could not be safely replayed.", 409)

        quota = quota_snapshot.to_dict() if quota_snapshot.exists else {"utc_day": utc_day, "count": 0}
        quota_count = quota.get("count")
        if (
            quota.get("utc_day") != utc_day
            or isinstance(quota_count, bool)
            or not isinstance(quota_count, int)
            or quota_count < 0
        ):
            raise DomainError("DATA_UNAVAILABLE", "Household creation limits could not be verified.", 503, True)
        if quota_count >= MAX_HOUSEHOLD_CREATIONS_PER_UTC_DAY:
            raise DomainError("HOUSEHOLD_CREATION_LIMIT", "The daily household creation limit has been reached.", 429, True)

        household_data: dict[str, Any] = {
            "schema_version": 1,
            "name": command.name,
            "created_at": created_at,
            "created_by": uid,
        }
        if command.address:
            household_data["address"] = command.address
        if command.lat is not None and command.lng is not None:
            household_data["location"] = {"lat": command.lat, "lng": command.lng}
        if command.place_id:
            household_data["place_id"] = command.place_id

        transaction.create(household_ref, household_data)
        transaction.create(
            member_ref,
            {
                "uid": uid,
                "role": "OWNER",
                "status": "ACTIVE",
                "created_at": created_at,
            },
        )
        transaction.create(
            request_ref,
            {
                "actor_uid": uid,
                "payload_hash": payload_hash,
                "result": result,
                "created_at": created_at,
            },
        )
        transaction.set(
            quota_ref,
            {"utc_day": utc_day, "count": quota_count + 1, "updated_at": created_at},
        )
        return result

    try:
        return commit(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("DATA_UNAVAILABLE", "The household could not be created.", 503, True) from exc


def delete_household(uid: str, household_id: str) -> dict[str, str]:
    if not isinstance(household_id, str) or not household_id:
        raise DomainError("VALIDATION_ERROR", "A valid household ID is required.", 400)
    db = get_firestore()
    household_ref = db.collection("households").document(household_id)
    member_ref = household_ref.collection("members").document(uid)

    @firestore.transactional
    def commit_delete(transaction: Any) -> dict[str, str]:
        household_snapshot = household_ref.get(transaction=transaction)
        if not household_snapshot.exists:
            raise DomainError("NOT_FOUND", "The household does not exist.", 404)
        member_snapshot = member_ref.get(transaction=transaction)
        if not member_snapshot.exists:
            raise DomainError("FORBIDDEN", "You are not a member of this household.", 403)
        member_data = member_snapshot.to_dict() or {}
        if member_data.get("role") != "OWNER" or member_data.get("status") != "ACTIVE":
            raise DomainError("FORBIDDEN", "Only an active owner can delete this household.", 403)

        # Mark membership revoked/deleted
        transaction.update(member_ref, {"status": "REVOKED", "deleted_at": datetime.now(timezone.utc)})
        # Delete or mark household document
        transaction.update(household_ref, {"status": "DELETED", "deleted_at": datetime.now(timezone.utc), "deleted_by": uid})
        return {"household_id": household_id, "status": "deleted"}

    try:
        return commit_delete(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError("DATA_UNAVAILABLE", "The household could not be deleted.", 503, True) from exc

