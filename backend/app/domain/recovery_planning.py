from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import uuid4

from firebase_admin import firestore
from pydantic import ValidationError

from app.agents.recovery import propose_collection_route
from app.core.errors import DomainError
from app.core.firestore import get_firestore
from app.core.identity import NgoPrincipal, Principal
from app.domain.surplus import (
    _assert_ngo,
    _ngo_idempotency_ref,
    _payload_hash,
    _retry_result,
    _serialize_surplus,
    list_central_surplus,
    require_surplus_pilot,
)
from app.schemas.surplus import (
    NgoRequestRecord,
    PlanNgoRequestCommand,
    RouteProposalCandidate,
    RouteProposalRecord,
    SurplusRecord,
)

MAX_SAVED_PROPOSAL_SCAN = 100
MAX_VISIBLE_PROPOSALS = 20


def _request_record(snapshot: Any, principal: NgoPrincipal) -> NgoRequestRecord:
    if not snapshot.exists:
        raise DomainError("NOT_FOUND", "The NGO request was not found.", 404)
    try:
        record = NgoRequestRecord.model_validate(snapshot.to_dict() or {})
    except ValidationError as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored NGO request data is invalid.", 503, True
        ) from exc
    if (
        record.request_id != snapshot.id
        or record.ngo_id != principal.ngo_id
        or record.requested_by != principal.uid
    ):
        raise DomainError("NOT_FOUND", "The NGO request was not found.", 404)
    return record


def _planner_request(record: NgoRequestRecord) -> dict[str, Any]:
    return {
        "request_id": record.request_id,
        "food_name": record.food_name,
        "category": record.category.value if record.category else None,
        "amount": str(record.amount),
        "unit": record.unit.value,
        "origin": record.origin.model_dump(mode="json"),
    }


def _planner_surplus(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "surplus_id",
        "version",
        "household_id",
        "status",
        "food_name",
        "category",
        "amount",
        "unit",
        "available_until",
        "location",
        "eligible",
        "demo_only",
    )
    return [{key: row[key] for key in keys} for row in rows[:100]]


def _matches(record: NgoRequestRecord, surplus: SurplusRecord) -> bool:
    exact_name = (
        record.food_name is not None
        and surplus.food_name.casefold() == record.food_name.casefold()
    )
    category_match = record.category is not None and surplus.category == record.category
    if record.food_name is not None and record.category is not None:
        return exact_name and category_match
    return exact_name if record.food_name is not None else category_match


def _expected_selection(
    record: NgoRequestRecord,
    surplus_rows: list[dict[str, Any]],
    now: datetime,
) -> list[tuple[SurplusRecord, Decimal]]:
    compatible = []
    for row in surplus_rows:
        try:
            option = SurplusRecord.model_validate(row)
        except ValidationError as exc:
            raise DomainError(
                "DATA_UNAVAILABLE", "Central surplus data is invalid.", 503, True
            ) from exc
        if (
            option.status.value == "CONFIRMED"
            and option.eligible is True
            and option.demo_only is True
            and option.available_until > now
            and option.unit == record.unit
            and _matches(record, option)
        ):
            compatible.append(option)
    compatible.sort(
        key=lambda option: (-option.amount, option.available_until, option.surplus_id)
    )
    remaining = record.amount
    selected: list[tuple[SurplusRecord, Decimal]] = []
    for option in compatible:
        if remaining <= 0 or len(selected) >= 10:
            break
        pickup = min(option.amount, remaining)
        selected.append((option, pickup))
        remaining -= pickup
    return selected


def _validate_candidate(
    record: NgoRequestRecord,
    surplus_rows: list[dict[str, Any]],
    candidate: RouteProposalCandidate,
    now: datetime,
) -> None:
    if candidate.request_id != record.request_id or candidate.unit != record.unit:
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "The proposal request scope is invalid.",
            502,
            True,
        )
    expected = _expected_selection(record, surplus_rows, now)
    expected_by_id = {
        option.surplus_id: (option, expected_pickup)
        for option, expected_pickup in expected
    }
    actual_ids = [stop.surplus_id for stop in candidate.selected_stops]
    if len(actual_ids) != len(set(actual_ids)) or set(actual_ids) != set(
        expected_by_id
    ):
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "The proposal selection is not the bounded deterministic match.",
            502,
            True,
        )

    matched = Decimal("0")
    for stop in candidate.selected_stops:
        option, expected_pickup = expected_by_id[stop.surplus_id]
        if (
            stop.version != option.version
            or stop.household_id != option.household_id
            or stop.food_name != option.food_name
            or stop.pickup_amount != expected_pickup
            or stop.unit != option.unit
            or stop.available_until != option.available_until
            or stop.location != option.location
        ):
            raise DomainError(
                "COLLECTION_PROPOSAL_INVALID",
                "The proposal changed a confirmed surplus fact.",
                502,
                True,
            )
        matched += stop.pickup_amount

    unmet = max(record.amount - matched, Decimal("0"))
    if candidate.matched_amount != matched or candidate.unmet_amount != unmet:
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "The proposal quantities are inconsistent.",
            502,
            True,
        )
    if not expected and candidate.route_status != "no_matches":
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "An empty proposal must report no matches.",
            502,
            True,
        )
    if expected and candidate.route_status == "no_matches":
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "A matched proposal cannot report no matches.",
            502,
            True,
        )
    if (
        candidate.route is not None
        and candidate.route.ordered_surplus_ids != actual_ids
    ):
        raise DomainError(
            "COLLECTION_PROPOSAL_INVALID",
            "The route order does not match the selected stops.",
            502,
            True,
        )


def _serialize_proposal(
    data: dict[str, Any], snapshot_id: str | None = None
) -> dict[str, Any]:
    try:
        record = RouteProposalRecord.model_validate(data)
    except ValidationError as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored route proposal data is invalid.", 503, True
        ) from exc
    if snapshot_id is not None and record.proposal_id != snapshot_id:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored route proposal identity is invalid.", 503, True
        )
    return record.model_dump(mode="json")


async def plan_ngo_request(
    principal: NgoPrincipal,
    request_id: str,
    command: PlanNgoRequestCommand,
) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    request_ref = db.collection("ngo_requests").document(request_id)
    request_record = _request_record(request_ref.get(), principal)
    if (
        request_record.status != "OPEN"
        or request_record.version != command.base_request_version
    ):
        raise DomainError(
            "VERSION_CONFLICT",
            "The NGO request changed. Reload it before planning.",
            409,
        )

    idem_ref = _ngo_idempotency_ref(
        db, f"plan:{request_id}", principal.uid, command.idempotency_key
    )
    payload_hash = _payload_hash(command)
    previous = _retry_result(idem_ref.get(), payload_hash, principal.uid)
    if previous is not None:
        return previous

    surplus_rows = list_central_surplus(principal)["surplus"]
    planner_rows = _planner_surplus(surplus_rows)
    candidate = await propose_collection_route(
        principal.uid,
        _planner_request(request_record),
        planner_rows,
    )
    now = datetime.now(timezone.utc)
    _validate_candidate(request_record, surplus_rows, candidate, now)
    proposal_id = uuid4().hex
    proposal_ref = db.collection("route_proposals").document(proposal_id)

    @firestore.transactional
    def commit(transaction: Any) -> dict[str, Any]:
        _assert_ngo(transaction, db, principal)
        previous_result = _retry_result(
            idem_ref.get(transaction=transaction), payload_hash, principal.uid
        )
        if previous_result is not None:
            return previous_result
        current_request = _request_record(
            request_ref.get(transaction=transaction), principal
        )
        if (
            current_request.status != "OPEN"
            or current_request.version != command.base_request_version
        ):
            raise DomainError(
                "VERSION_CONFLICT",
                "The NGO request changed while the route was being planned.",
                409,
            )

        refs = [
            db.collection("households")
            .document(stop.household_id)
            .collection("surplus_submissions")
            .document(stop.surplus_id)
            for stop in candidate.selected_stops
        ]
        snapshots = [ref.get(transaction=transaction) for ref in refs]
        current_rows = []
        for stop, snapshot in zip(candidate.selected_stops, snapshots, strict=True):
            if not snapshot.exists:
                raise DomainError(
                    "VERSION_CONFLICT",
                    "A selected surplus submission is no longer available.",
                    409,
                )
            row = _serialize_surplus(snapshot.to_dict() or {}, snapshot.id)
            if row["household_id"] != stop.household_id:
                raise DomainError(
                    "VERSION_CONFLICT", "A selected surplus scope changed.", 409
                )
            current_rows.append(row)
        _validate_candidate(
            current_request, current_rows, candidate, datetime.now(timezone.utc)
        )

        stored = candidate.model_dump(mode="json") | {
            "schema_version": 1,
            "proposal_id": proposal_id,
            "ngo_id": principal.ngo_id,
            "created_by": principal.uid,
            "request_version": current_request.version,
            "origin": current_request.origin.model_dump(mode="json"),
            "created_at": now,
        }
        result = {"proposal": _serialize_proposal(stored)}
        transaction.create(proposal_ref, stored)
        transaction.update(
            request_ref,
            {
                "status": "PLANNED",
                "version": current_request.version + 1,
                "updated_at": now,
                "proposal_id": proposal_id,
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
            "DATA_UNAVAILABLE", "The route proposal could not be saved.", 503, True
        ) from exc


def _proposal_validity(
    db: Any, proposal: RouteProposalRecord
) -> tuple[str, str | None]:
    now = datetime.now(timezone.utc)
    refs = [
        db.collection("households")
        .document(stop.household_id)
        .collection("surplus_submissions")
        .document(stop.surplus_id)
        for stop in proposal.selected_stops
    ]
    snapshots = list(db.get_all(refs)) if refs else []
    by_path = {snapshot.reference.path: snapshot for snapshot in snapshots}
    for stop, ref in zip(proposal.selected_stops, refs, strict=True):
        snapshot = by_path.get(ref.path)
        if snapshot is None or not snapshot.exists:
            return "STALE", "A selected submission is no longer available."
        try:
            current = SurplusRecord.model_validate(snapshot.to_dict() or {})
        except ValidationError:
            return "STALE", "A selected submission can no longer be verified."
        if (
            current.status.value != "CONFIRMED"
            or current.version != stop.version
            or current.available_until <= now
        ):
            return "STALE", "A selected submission changed, expired, or was cancelled."
    return "CURRENT", None


def _listed_proposal(db: Any, snapshot: Any) -> dict[str, Any]:
    proposal = RouteProposalRecord.model_validate(snapshot.to_dict() or {})
    if proposal.proposal_id != snapshot.id:
        raise DomainError(
            "DATA_UNAVAILABLE", "Stored route proposal identity is invalid.", 503, True
        )
    row = proposal.model_dump(mode="json")
    validity, reason = _proposal_validity(db, proposal)
    row["validity"] = validity
    row["stale_reason"] = reason
    return row


def _household_proposal(db: Any, snapshot: Any, household_id: str) -> dict[str, Any]:
    proposal = _listed_proposal(db, snapshot)
    own_stops = [
        stop
        for stop in proposal["selected_stops"]
        if stop["household_id"] == household_id
    ]
    return {
        "proposal_id": proposal["proposal_id"],
        "request_id": proposal["request_id"],
        "selected_stops": own_stops,
        "matched_amount": proposal["matched_amount"],
        "unmet_amount": proposal["unmet_amount"],
        "unit": proposal["unit"],
        "route_status": proposal["route_status"],
        "route_available": proposal["route"] is not None,
        "explanation": (
            "This household is included in an advisory collection proposal. "
            "Other households' exact stops and the full route are limited to the "
            "allowlisted demo NGO."
        ),
        "warnings": [
            "No food is reserved and no driver has been dispatched.",
            (
                "The full route is hidden from household accounts to protect other "
                "pickup locations."
            ),
        ],
        "created_at": proposal["created_at"],
        "validity": proposal["validity"],
        "stale_reason": proposal["stale_reason"],
        "demo_only": True,
    }


def list_ngo_proposals(principal: NgoPrincipal) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    try:
        snapshots = (
            db.collection("route_proposals")
            .order_by("created_at", direction="DESCENDING")
            .limit(MAX_SAVED_PROPOSAL_SCAN)
            .stream()
        )
        rows = []
        for snapshot in snapshots:
            data = snapshot.to_dict() or {}
            if (
                data.get("ngo_id") != principal.ngo_id
                or data.get("created_by") != principal.uid
            ):
                continue
            rows.append(_listed_proposal(db, snapshot))
            if len(rows) >= MAX_VISIBLE_PROPOSALS:
                break
        return {"proposals": rows, "demo_only": True}
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Route proposals are unavailable.", 503, True
        ) from exc


def list_household_proposals(principal: Principal) -> dict[str, Any]:
    require_surplus_pilot()
    db = get_firestore()
    try:
        snapshots = (
            db.collection("route_proposals")
            .order_by("created_at", direction="DESCENDING")
            .limit(MAX_SAVED_PROPOSAL_SCAN)
            .stream()
        )
        rows = []
        for snapshot in snapshots:
            data = snapshot.to_dict() or {}
            selected = data.get("selected_stops")
            if not isinstance(selected, list) or not any(
                isinstance(stop, dict)
                and stop.get("household_id") == principal.household_id
                for stop in selected
            ):
                continue
            rows.append(_household_proposal(db, snapshot, principal.household_id))
            if len(rows) >= MAX_VISIBLE_PROPOSALS:
                break
        return {"proposals": rows, "demo_only": True}
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "DATA_UNAVAILABLE", "Household route proposals are unavailable.", 503, True
        ) from exc
