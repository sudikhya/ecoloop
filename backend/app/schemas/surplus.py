from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.schemas.household import IdempotencyKey, OpaqueId, StrictModel


def _reject_boolean_decimal(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("boolean values are not quantities")
    return value


PositiveAmount = Annotated[
    Decimal,
    BeforeValidator(_reject_boolean_decimal),
    Field(gt=0, max_digits=10, decimal_places=3),
]
FoodName = Annotated[str, StringConstraints(min_length=1, max_length=100)]
Address = Annotated[str, StringConstraints(min_length=1, max_length=300)]
PlaceId = Annotated[str, StringConstraints(min_length=1, max_length=300)]


class FoodCategory(StrEnum):
    PRODUCE = "produce"
    GRAINS = "grains"
    BAKERY = "bakery"
    DAIRY = "dairy"
    PACKAGED = "packaged"
    PREPARED_FOOD = "prepared_food"
    OTHER = "other"


class FoodUnit(StrEnum):
    GRAM = "g"
    KILOGRAM = "kg"
    MILLILITRE = "ml"
    LITRE = "l"
    PORTION = "portion"
    PIECE = "piece"
    PACK = "pack"


class PreparationState(StrEnum):
    UNPREPARED = "unprepared"
    UNSERVED_PREPARED = "unserved_prepared"
    PACKAGED = "packaged"


class PackagingState(StrEnum):
    SEALED = "sealed"
    COVERED = "covered"
    OPEN = "open"
    UNPACKAGED = "unpackaged"


class SourceModality(StrEnum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    MANUAL = "manual"


class SurplusStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class LocationInput(StrictModel):
    address: Address
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    place_id: PlaceId | None = None


class SurplusDetails(StrictModel):
    food_name: FoodName
    category: FoodCategory
    amount: PositiveAmount
    unit: FoodUnit
    preparation_state: PreparationState
    packaging_state: PackagingState
    available_until: datetime
    source_modality: SourceModality
    household_location_confirmed: Literal[True]
    not_plate_leftover: Literal[True]
    not_spoiled: Literal[True]
    not_expired: Literal[True]
    not_previously_served: Literal[True]

    @field_validator("available_until")
    @classmethod
    def require_aware_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("available_until must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_prepared_food(self) -> SurplusDetails:
        if (
            self.category == FoodCategory.PREPARED_FOOD
            and self.preparation_state != PreparationState.UNSERVED_PREPARED
        ):
            raise ValueError(
                "prepared food must be explicitly confirmed as unserved prepared food"
            )
        return self


class ConfirmSurplusCommand(SurplusDetails):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey


class UpdateSurplusCommand(SurplusDetails):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    base_version: int = Field(ge=1, le=1_000_000)


class CancelSurplusCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    base_version: int = Field(ge=1, le=1_000_000)


class SurplusIntakeTextCommand(StrictModel):
    schema_version: Literal[1] = 1
    text: Annotated[str, StringConstraints(min_length=1, max_length=8_000)]


class NgoRequestCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    food_name: FoodName | None = None
    category: FoodCategory | None = None
    amount: PositiveAmount
    unit: FoodUnit
    origin: LocationInput

    @model_validator(mode="after")
    def require_food_or_category(self) -> NgoRequestCommand:
        if self.food_name is None and self.category is None:
            raise ValueError("food_name or category is required")
        return self


class PlanNgoRequestCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    base_request_version: int = Field(ge=1, le=1_000_000)


class SurplusRecord(StrictModel):
    schema_version: Literal[1]
    surplus_id: OpaqueId
    household_id: OpaqueId
    owner_uid: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    status: SurplusStatus
    version: int = Field(ge=1)
    food_name: FoodName
    category: FoodCategory
    amount: PositiveAmount
    unit: FoodUnit
    preparation_state: PreparationState
    packaging_state: PackagingState
    available_until: datetime
    location: LocationInput
    source_modality: SourceModality
    eligible: Literal[True]
    safety_certified: Literal[False]
    requires_qualified_review: bool
    demo_only: Literal[True]
    created_at: datetime
    updated_at: datetime
    updated_by: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class NgoRequestRecord(StrictModel):
    schema_version: Literal[1]
    request_id: OpaqueId
    ngo_id: OpaqueId
    requested_by: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    food_name: FoodName | None = None
    category: FoodCategory | None = None
    amount: PositiveAmount
    unit: FoodUnit
    origin: LocationInput
    status: Literal["OPEN", "PLANNED"]
    version: int = Field(ge=1)
    demo_only: Literal[True]
    created_at: datetime
    updated_at: datetime


class SurplusCandidate(StrictModel):
    food_name: FoodName | None = None
    category: FoodCategory | None = None
    amount: PositiveAmount | None = None
    unit: FoodUnit | None = None
    preparation_state: Literal[
        "unprepared", "unserved_prepared", "packaged", "unknown"
    ] = "unknown"
    packaging_state: Literal["sealed", "covered", "open", "unpackaged", "unknown"] = (
        "unknown"
    )
    unknown_fields: list[
        Literal[
            "food_name",
            "category",
            "amount",
            "unit",
            "preparation_state",
            "packaging_state",
        ]
    ] = Field(default_factory=list, max_length=6)
    review_flags: list[
        Literal[
            "ambiguous_input",
            "multiple_foods_detected",
            "possible_plate_leftovers",
            "possible_spoilage",
            "possible_expiry",
            "prepared_food_requires_qualified_review",
            "amount_needs_confirmation",
            "unit_needs_confirmation",
            "packaging_needs_confirmation",
        ]
    ] = Field(default_factory=list, max_length=9)
    disposition: Literal["review", "do_not_share"]
    evidence_note: Annotated[str, StringConstraints(min_length=1, max_length=240)]

    @model_validator(mode="after")
    def keep_amount_and_unit_together(self) -> SurplusCandidate:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must both be known or both be unknown")
        return self


class SurplusIntakeResult(StrictModel):
    source_modality: Literal["text", "image", "audio", "unknown"]
    candidates: list[SurplusCandidate] = Field(max_length=12)
    summary: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    requires_household_confirmation: Literal[True]
    safety_certified: Literal[False]
    demo_only: Literal[True]


class SelectedSurplusStop(StrictModel):
    surplus_id: OpaqueId
    version: int = Field(ge=1)
    household_id: OpaqueId
    food_name: FoodName
    pickup_amount: PositiveAmount
    unit: FoodUnit
    available_until: datetime
    location: LocationInput


class RouteFacts(StrictModel):
    distance_meters: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    encoded_polyline: Annotated[
        str, StringConstraints(min_length=1, max_length=200_000)
    ]
    ordered_surplus_ids: list[OpaqueId] = Field(min_length=1, max_length=10)


class RouteProposalCandidate(StrictModel):
    request_id: OpaqueId
    selected_stops: list[SelectedSurplusStop] = Field(max_length=10)
    matched_amount: Decimal = Field(ge=0, max_digits=10, decimal_places=3)
    unmet_amount: Decimal = Field(ge=0, max_digits=10, decimal_places=3)
    unit: FoodUnit
    route_status: Literal["ready", "unavailable", "no_matches"]
    route: RouteFacts | None = None
    explanation: Annotated[str, StringConstraints(min_length=1, max_length=600)]
    warnings: list[Annotated[str, StringConstraints(min_length=1, max_length=240)]] = (
        Field(
            default_factory=list,
            max_length=8,
        )
    )
    advisory_only: Literal[True]
    demo_only: Literal[True]

    @model_validator(mode="after")
    def validate_route_coherence(self) -> RouteProposalCandidate:
        if self.route_status == "ready" and self.route is None:
            raise ValueError("ready route requires route facts")
        if self.route_status != "ready" and self.route is not None:
            raise ValueError("unavailable or empty routes must not include route facts")
        if self.route_status == "no_matches" and self.selected_stops:
            raise ValueError("no_matches must not include stops")
        return self


class RouteProposalRecord(RouteProposalCandidate):
    schema_version: Literal[1]
    proposal_id: OpaqueId
    ngo_id: OpaqueId
    created_by: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    request_version: int = Field(ge=1)
    origin: LocationInput
    created_at: datetime
