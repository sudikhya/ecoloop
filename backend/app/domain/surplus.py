from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from firebase_admin import firestore
from pydantic import ValidationError

from app.core.config import settings
from app.core.errors import DomainError
from app.core.firestore import get_firestore
from app.core.identity import NgoPrincipal, Principal
from app.schemas.surplus import (
    CancelSurplusCommand,
    ConfirmSurplusCommand,
    NgoRequestCommand,
    NgoRequestRecord,
    SurplusRecord,
    UpdateSurplusCommand,
)

MAX_HOUSEHOLD_SURPLUS_READS = 200
MAX_CENTRAL_SURPLUS_READS = 500


def require_surplus_pilot() -> None:
    if not settings.SURPLUS_PILOT_ENABLED:
        raise DomainError(
            "SURPLUS_PILOT_DISABLED",
            "The demo surplus pilot is not enabled.",
            503,
            retryable=False,
        )


def _payload_hash(command: Any) -> str:
    canonical = json.dumps(
        command.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _actor_scope(uid: str) -> str:
    return hashlib.sha256(uid.encode("utf-8")).hexdigest()


def _household_idempotency_ref(
    household_ref: Any, operation: str, uid: str, key: str
) -> Any:
    key_scope = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return household_ref.collection("surplus_idempotency").document(
        f"{operation}:{_actor_scope(uid)}:{key_scope}"
    )


def _ngo_idempotency_ref(db: Any, operation: str, uid: str, key: str) -> Any:
    key_scope = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return (
        db.collection("ngo_accounts")
        .document(uid)
        .collection("idempotency")
        .document(f"{operation}:{key_scope}")
    )


def _retry_result(
    snapshot: Any, payload_hash: str, actor_uid: str
) -> dict[str, Any] | None:
    if not snapshot.exists:
        return None
    data = snapshot.to_dict() or {}
    if data.get("actor_uid") != actor_uid or data.get("payload_hash") != payload_hash:
        raise DomainError(
            "IDEMPOTENCY_CONFLICT",
            "This request key was already used for a different command.",
            409,
        )
    result = data.get("result")
    if not isinstance(result, dict):
        raise DomainError(
            "DATA_UNAVAILABLE", "The saved command result is unavailable.", 503, True
        )
    return result


def _assert_household_member(
    transaction: Any, db: Any, principal: Principal
) -> dict[str, Any]:
    household_ref = db.collection("households").document(principal.household_id)
    member_ref = household_ref.collection("members").document(principal.uid)
    household_snapshot = household_ref.get(transaction=transaction)
    member_snapshot = member_ref.get(transaction=transaction)
    household = household_snapshot.to_dict() if household_snapshot.exists else None
    member = member_snapshot.to_dict() if member_snapshot.exists else None
    if (
        not household
        or household.get("status") == "DELETED"
        or not member
        or member.get("uid") != principal.uid
        or member.get("status") != "ACTIVE"
        or member.get("role") != principal.role
    ):
        raise DomainError(
            "FORBIDDEN", "The requested household membership is not available.", 403
        )
    return household


def _assert_ngo(transaction: Any, db: Any, principal: NgoPrincipal) -> None:
    snapshot = (
        db.collection("ngo_accounts")
        .document(principal.uid)
        .get(transaction=transaction)
    )
    data = snapshot.to_dict() if snapshot.exists else None
    if (
        not data
        or data.get("uid") != principal.uid
        or data.get("ngo_id") != principal.ngo_id
        or data.get("role") != "NGO"
        or data.get("status") != "ACTIVE"
        or data.get("demo_only") is not True
    ):
        raise DomainError("FORBIDDEN", "The NGO pilot role is not available.", 403)


def _household_location(household: dict[str, Any]) -> dict[str, Any]:
    address = household.get("address")
    raw_location = household.get("location")
    latitude = raw_location.get("lat") if isinstance(raw_location, dict) else None
    longitude = raw_location.get("lng") if isinstance(raw_location, dict) else None
    if (
        not isinstance(address, str)
        or not address.strip()
        or isinstance(latitude, bool)
        or not isinstance(latitude, (int, float))
        or isinstance(longitude, bool)
        or not isinstance(longitude, (int, float))
        or not -90 <= latitude <= 90
        or not -180 <= longitude <= 180
    ):
        raise DomainError(
            "HOUSEHOLD_LOCATION_REQUIRED",
            "Add and confirm a mapped household location before sharing surplus.",
            422,
        )
    location: dict[str, Any] = {
        "address": address.strip(),
        "latitude": float(latitude),
        "longitude": float(longitude),
    }
    place_id = household.get("place_id")
    if isinstance(place_id, str) and place_id.strip():
        location["place_id"] = place_id.strip()
    return location


def _stored_surplus(
    *,
    surplus_id: str,
    principal: Principal,
    command: ConfirmSurplusCommand | UpdateSurplusCommand,
    location: dict[str, Any],
    now: datetime,
    version: int,
    created_at: datetime,
) -> dict[str, Any]:
    if command.available_until <= now:
        raise DomainError(
            "INVALID_AVAILABILITY",
            "The availability deadline must be in the future.",
            422,
        )
    requires_qualified_review = command.category.value == "prepared_food"
    return {
        "schema_version": 1,
        "surplus_id": surplus_id,
        "household_id": principal.household_id,
        "owner_uid": principal.uid,
        "status": "CONFIRMED",
        "version": version,
        "food_name": command.food_name,
        "category": command.category.value,
        "amount": str(command.amount),
        "unit": command.unit.value,
        "preparation_state": command.preparation_state.value,
        "packaging_state": command.packaging_state.value,
        "available_until": command.available_until,
        "location": location,
        "source_modality": command.source_modality.value,
        "eligible": True,
        "safety_certified": False,
        "requires_qualified_review": requires_qualified_review,
        "demo_only": True,
        "created_at": created_at,
        "updated_at": now,
        "updated_by": principal.uid,
    }


def _serialize_surplus(
    data: dict[str, Any], snapshot_id: str | None = None
) -> dict[str, Any]:
    try:
        record = SurplusRecord.model_validate(data)
    except ValidationError as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored surplus data is invalid.", 503, True
        ) from exc
    if snapshot_id is not None and record.surplus_id != snapshot_id:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored surplus identity is invalid.", 503, True
        )
    return record.model_dump(mode="json")


def confirm_surplus(
    principal: Principal, command: ConfirmSurplusCommand
) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    household_ref = db.collection("households").document(principal.household_id)
    surplus_id = uuid4().hex
    surplus_ref = household_ref.collection("surplus_submissions").document(surplus_id)
    idem_ref = _household_idempotency_ref(
        household_ref, "confirm", principal.uid, command.idempotency_key
    )
    payload_hash = _payload_hash(command)
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, Any]:
        household = _assert_household_member(transaction, db, principal)
        previous = _retry_result(
            idem_ref.get(transaction=transaction), payload_hash, principal.uid
        )
        if previous is not None:
            return previous
        if surplus_ref.get(transaction=transaction).exists:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "The surplus record could not be safely created.",
                409,
            )
        stored = _stored_surplus(
            surplus_id=surplus_id,
            principal=principal,
            command=command,
            location=_household_location(household),
            now=now,
            version=1,
            created_at=now,
        )
        result = {"surplus": _serialize_surplus(stored)}
        transaction.create(surplus_ref, stored)
        transaction.create(
            idem_ref,
            {
                "actor_uid": principal.uid,
                "payload_hash": payload_hash,
                "result": result,
                "created_at": now,
            },
        )
        return result

    try:
        return commit(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE",
            "The surplus submission could not be confirmed.",
            503,
            True,
        ) from exc


def update_surplus(
    principal: Principal, surplus_id: str, command: UpdateSurplusCommand
) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    household_ref = db.collection("households").document(principal.household_id)
    surplus_ref = household_ref.collection("surplus_submissions").document(surplus_id)
    idem_ref = _household_idempotency_ref(
        household_ref, f"update:{surplus_id}", principal.uid, command.idempotency_key
    )
    payload_hash = _payload_hash(command)
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, Any]:
        household = _assert_household_member(transaction, db, principal)
        previous = _retry_result(
            idem_ref.get(transaction=transaction), payload_hash, principal.uid
        )
        if previous is not None:
            return previous
        snapshot = surplus_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise DomainError("NOT_FOUND", "The surplus submission was not found.", 404)
        current = snapshot.to_dict() or {}
        if (
            current.get("household_id") != principal.household_id
            or current.get("status") != "CONFIRMED"
        ):
            raise DomainError(
                "VERSION_CONFLICT", "The surplus submission is no longer editable.", 409
            )
        version = current.get("version")
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != command.base_version
        ):
            raise DomainError(
                "VERSION_CONFLICT",
                "The surplus submission changed. Reload it before editing.",
                409,
            )
        created_at = current.get("created_at")
        if not isinstance(created_at, datetime):
            raise DomainError(
                "DATA_UNAVAILABLE", "Stored surplus data is invalid.", 503, True
            )
        stored = _stored_surplus(
            surplus_id=surplus_id,
            principal=principal,
            command=command,
            location=_household_location(household),
            now=now,
            version=version + 1,
            created_at=created_at,
        )
        result = {"surplus": _serialize_surplus(stored)}
        transaction.set(surplus_ref, stored)
        transaction.create(
            idem_ref,
            {
                "actor_uid": principal.uid,
                "payload_hash": payload_hash,
                "result": result,
                "created_at": now,
            },
        )
        return result

    try:
        return commit(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE",
            "The surplus submission could not be updated.",
            503,
            True,
        ) from exc


def cancel_surplus(
    principal: Principal, surplus_id: str, command: CancelSurplusCommand
) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    household_ref = db.collection("households").document(principal.household_id)
    surplus_ref = household_ref.collection("surplus_submissions").document(surplus_id)
    idem_ref = _household_idempotency_ref(
        household_ref, f"cancel:{surplus_id}", principal.uid, command.idempotency_key
    )
    payload_hash = _payload_hash(command)
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, Any]:
        _assert_household_member(transaction, db, principal)
        previous = _retry_result(
            idem_ref.get(transaction=transaction), payload_hash, principal.uid
        )
        if previous is not None:
            return previous
        snapshot = surplus_ref.get(transaction=transaction)
        if not snapshot.exists:
            raise DomainError("NOT_FOUND", "The surplus submission was not found.", 404)
        current = snapshot.to_dict() or {}
        version = current.get("version")
        if (
            current.get("household_id") != principal.household_id
            or current.get("status") != "CONFIRMED"
        ):
            raise DomainError(
                "VERSION_CONFLICT", "The surplus submission is no longer active.", 409
            )
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version != command.base_version
        ):
            raise DomainError(
                "VERSION_CONFLICT",
                "The surplus submission changed. Reload it before cancelling.",
                409,
            )
        next_version = version + 1
        result = {
            "surplus_id": surplus_id,
            "status": "CANCELLED",
            "version": next_version,
        }
        transaction.update(
            surplus_ref,
            {
                "status": "CANCELLED",
                "version": next_version,
                "updated_at": now,
                "updated_by": principal.uid,
            },
        )
        transaction.create(
            idem_ref,
            {
                "actor_uid": principal.uid,
                "payload_hash": payload_hash,
                "result": result,
                "created_at": now,
            },
        )
        return result

    try:
        return commit(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE",
            "The surplus submission could not be cancelled.",
            503,
            True,
        ) from exc


def list_household_surplus(principal: Principal) -> dict[str, Any]:
    require_surplus_pilot()
    try:
        snapshots = (
            get_firestore()
            .collection("households")
            .document(principal.household_id)
            .collection("surplus_submissions")
            .limit(MAX_HOUSEHOLD_SURPLUS_READS)
            .stream()
        )
        rows = []
        for snapshot in snapshots:
            row = _serialize_surplus(snapshot.to_dict() or {}, snapshot.id)
            if row["household_id"] != principal.household_id:
                raise DomainError(
                    "DATA_UNAVAILABLE", "Stored surplus scope is invalid.", 503, True
                )
            rows.append(row)
        rows.sort(key=lambda row: (row["created_at"], row["surplus_id"]), reverse=True)
        return {"surplus": rows}
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Household surplus is unavailable.", 503, True
        ) from exc


def list_central_surplus(principal: NgoPrincipal) -> dict[str, Any]:
    require_surplus_pilot()
    now = datetime.now(timezone.utc)
    try:
        snapshots = (
            get_firestore()
            .collection_group("surplus_submissions")
            .limit(MAX_CENTRAL_SURPLUS_READS)
            .stream()
        )
        rows = []
        for snapshot in snapshots:
            row = _serialize_surplus(snapshot.to_dict() or {}, snapshot.id)
            if row["status"] != "CONFIRMED" or row["eligible"] is not True:
                continue
            deadline = datetime.fromisoformat(row["available_until"])
            if deadline <= now:
                continue
            row.pop("owner_uid", None)
            rows.append(row)
        rows.sort(key=lambda row: (row["available_until"], row["surplus_id"]))
        return {
            "surplus": rows[:MAX_HOUSEHOLD_SURPLUS_READS],
            "demo_only": True,
            "ngo_id": principal.ngo_id,
        }
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Central surplus is unavailable.", 503, True
        ) from exc


def create_ngo_request(
    principal: NgoPrincipal, command: NgoRequestCommand
) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    request_id = uuid4().hex
    request_ref = db.collection("ngo_requests").document(request_id)
    idem_ref = _ngo_idempotency_ref(
        db, "request", principal.uid, command.idempotency_key
    )
    payload_hash = _payload_hash(command)
    now = datetime.now(timezone.utc)

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, Any]:
        _assert_ngo(transaction, db, principal)
        previous = _retry_result(
            idem_ref.get(transaction=transaction), payload_hash, principal.uid
        )
        if previous is not None:
            return previous
        if request_ref.get(transaction=transaction).exists:
            raise DomainError(
                "IDEMPOTENCY_CONFLICT",
                "The NGO request could not be safely created.",
                409,
            )
        stored = {
            "schema_version": 1,
            "request_id": request_id,
            "ngo_id": principal.ngo_id,
            "requested_by": principal.uid,
            "food_name": command.food_name,
            "category": command.category.value if command.category else None,
            "amount": str(command.amount),
            "unit": command.unit.value,
            "origin": command.origin.model_dump(mode="json"),
            "status": "OPEN",
            "version": 1,
            "demo_only": True,
            "created_at": now,
            "updated_at": now,
        }
        try:
            record = NgoRequestRecord.model_validate(stored).model_dump(mode="json")
        except ValidationError as exc:
            raise DomainError(
                "VALIDATION_ERROR", "The NGO request could not be validated.", 422
            ) from exc
        result = {"request": record}
        transaction.create(request_ref, stored)
        transaction.create(
            idem_ref,
            {
                "actor_uid": principal.uid,
                "payload_hash": payload_hash,
                "result": result,
                "created_at": now,
            },
        )
        return result

    try:
        return commit(db.transaction())
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "The NGO request could not be created.", 503, True
        ) from exc
