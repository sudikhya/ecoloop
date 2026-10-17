from __future__ import annotations

from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal
from unicodedata import category

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints, StrictInt, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


OpaqueId = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
ItemName = Annotated[str, StringConstraints(min_length=1, max_length=120)]
UnitName = Annotated[str, StringConstraints(min_length=1, max_length=32, pattern=r"^[A-Za-z][A-Za-z0-9_-]*$")]
IdempotencyKey = Annotated[str, StringConstraints(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
HouseholdDisplayName = Annotated[str, StringConstraints(min_length=1, max_length=60)]


def _reject_boolean_number(value: object) -> object:
    if isinstance(value, bool):
        raise ValueError("boolean values are not quantities")
    return value


Amount = Annotated[float, BeforeValidator(_reject_boolean_number), Field(gt=0, le=1_000_000, allow_inf_nan=False)]
NonNegativeAmount = Annotated[
    float,
    BeforeValidator(_reject_boolean_number),
    Field(ge=0, le=1_000_000, allow_inf_nan=False),
]


class DateType(StrEnum):
    USE_BY = "USE_BY"
    EXPIRY = "EXPIRY"
    BEST_BEFORE = "BEST_BEFORE"
    USER_TARGET = "USER_TARGET"
    UNKNOWN = "UNKNOWN"


class FoodSource(StrEnum):
    USER = "USER"


class OutcomeType(StrEnum):
    USED = "USED"
    STORED = "STORED"
    DISCARDED = "DISCARDED"
    HANDED_OVER = "HANDED_OVER"
    COMPOSTED = "COMPOSTED"


class MeasurementBasis(StrEnum):
    MEASURED = "MEASURED"
    USER_ESTIMATED = "USER_ESTIMATED"
    UNKNOWN = "UNKNOWN"


class ShareState(StrEnum):
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    HANDED_OVER = "HANDED_OVER"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class ShareCondition(StrEnum):
    UNSERVED_USER_REPORTED = "UNSERVED_USER_REPORTED"
    EXPIRED = "EXPIRED"
    SPOILED = "SPOILED"
    PLATED = "PLATED"
    UNKNOWN = "UNKNOWN"


class FoodObservationInput(StrictModel):
    item_id: OpaqueId
    base_version: Annotated[StrictInt, Field(ge=0)]
    name: ItemName
    amount: NonNegativeAmount | None = None
    unit: UnitName | None = None
    date_value: date | None = None
    date_type: DateType = DateType.UNKNOWN
    date_source: FoodSource | None = None
    storage: Annotated[str, StringConstraints(max_length=120)] | None = None
    source: Literal["USER"] = "USER"

    @model_validator(mode="after")
    def validate_observation(self) -> FoodObservationInput:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        if (self.date_value is None) != (self.date_type == DateType.UNKNOWN):
            raise ValueError("date_value and a known date_type must be provided together")
        if self.date_value is None and self.date_source is not None:
            raise ValueError("unknown dates must not include a date_source")
        if self.date_value is not None and self.date_source is None:
            raise ValueError("date_source is required when a date is provided")
        return self


class ConfirmFactsCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    observations: Annotated[list[FoodObservationInput], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def unique_item_ids(self) -> ConfirmFactsCommand:
        ids = [observation.item_id for observation in self.observations]
        if len(ids) != len(set(ids)):
            raise ValueError("item_id values must be unique within a command")
        return self


class RecordOutcomeCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    outcome_id: OpaqueId
    item_id: OpaqueId
    plan_id: OpaqueId | None = None
    base_version: Annotated[StrictInt, Field(ge=1)]
    outcome_type: OutcomeType
    amount: Amount | None = None
    unit: UnitName | None = None
    measurement_basis: MeasurementBasis = MeasurementBasis.UNKNOWN
    storage: Annotated[str, StringConstraints(min_length=1, max_length=120)] | None = None
    occurred_at: datetime
    reverses_event_id: OpaqueId | None = None

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_quantity(self) -> RecordOutcomeCommand:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        if self.amount is None and self.measurement_basis != MeasurementBasis.UNKNOWN:
            raise ValueError("measurement_basis must be UNKNOWN when amount is unknown")
        if self.amount is not None and self.measurement_basis == MeasurementBasis.UNKNOWN:
            raise ValueError("measured amount requires a measurement basis")
        if (self.storage is not None) != (self.outcome_type == OutcomeType.STORED):
            raise ValueError("storage must be provided only for a stored outcome")
        if self.reverses_event_id is not None:
            raise ValueError("outcome reversals are not supported until atomic reversal behavior is implemented")
        if self.outcome_type == OutcomeType.HANDED_OVER:
            raise ValueError("handed-over outcomes must be recorded through an eligible share log")
        return self


class CreateShareLogCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    share_id: OpaqueId
    item_id: OpaqueId
    base_item_version: Annotated[StrictInt, Field(ge=1)]
    recipient_label: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    amount: Amount | None = None
    unit: UnitName | None = None
    measurement_basis: MeasurementBasis = MeasurementBasis.UNKNOWN
    condition: ShareCondition
    freshness: Literal["UNKNOWN"] = "UNKNOWN"
    note: Annotated[str, StringConstraints(max_length=500)] | None = None
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_share(self) -> CreateShareLogCommand:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        if self.amount is None and self.measurement_basis != MeasurementBasis.UNKNOWN:
            raise ValueError("measurement_basis must be UNKNOWN when amount is unknown")
        if self.amount is not None and self.measurement_basis == MeasurementBasis.UNKNOWN:
            raise ValueError("a known amount requires a measurement basis")
        return self


class TransitionShareLogCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    base_version: Annotated[StrictInt, Field(ge=1)]
    state: Literal[ShareState.ACCEPTED, ShareState.HANDED_OVER, ShareState.CANCELLED, ShareState.EXPIRED]
    occurred_at: datetime
    condition: ShareCondition | None = None
    expected_item_version: Annotated[StrictInt, Field(ge=1)] | None = None
    amount: Amount | None = None
    unit: UnitName | None = None
    measurement_basis: MeasurementBasis = MeasurementBasis.UNKNOWN

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_transition(self) -> TransitionShareLogCommand:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        if self.state == ShareState.HANDED_OVER:
            if self.expected_item_version is None:
                raise ValueError("expected_item_version is required for a handover")
            if self.condition is None:
                raise ValueError("condition is required for a handover")
            if self.amount is None and self.measurement_basis != MeasurementBasis.UNKNOWN:
                raise ValueError("measurement_basis must be UNKNOWN when handover amount is unknown")
            if self.amount is not None and self.measurement_basis == MeasurementBasis.UNKNOWN:
                raise ValueError("a known handover amount requires a measurement basis")
        elif self.expected_item_version is not None or self.amount is not None or self.unit is not None or self.measurement_basis != MeasurementBasis.UNKNOWN or self.condition is not None:
            raise ValueError("handover quantity, condition and item version are only allowed for HANDED_OVER")
        return self


class ShoppingEntryInput(StrictModel):
    entry_id: OpaqueId
    base_version: Annotated[StrictInt, Field(ge=0)]
    item_name: ItemName
    desired_amount: Amount | None = None
    unit: UnitName | None = None

    @model_validator(mode="after")
    def validate_quantity(self) -> ShoppingEntryInput:
        if (self.desired_amount is None) != (self.unit is None):
            raise ValueError("desired_amount and unit must be provided together")
        return self


class ShoppingCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    entry: ShoppingEntryInput


class CreateHouseholdCommand(StrictModel):
    schema_version: Literal[1] = 1
    idempotency_key: IdempotencyKey
    name: HouseholdDisplayName
    address: Annotated[str, StringConstraints(min_length=1, max_length=256)] | None = None
    lat: float | None = None
    lng: float | None = None
    place_id: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None

    @field_validator("name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        if any(category(character) == "Cc" for character in value):
            raise ValueError("name must be a single-line display name")
        return value



class ApiResult(StrictModel):
    schema_version: Literal[1] = 1
    request_id: str
    result: dict[str, object]


class ProposalBase(StrictModel):
    proposal_id: OpaqueId
    schema_version: Literal[1] = 1
    version: Annotated[StrictInt, Field(ge=1)]
    base_version: Annotated[StrictInt, Field(ge=0)]
    scope: Literal["HOUSEHOLD"] = "HOUSEHOLD"
    status: Literal["PENDING"] = "PENDING"
    source_refs: Annotated[list[OpaqueId], Field(max_length=50)] = Field(default_factory=list)
    allowed_actions: Annotated[
        list[Literal["APPROVE", "EDIT", "DISMISS", "ADD", "SKIP", "CONFIRM_STOCK", "USE", "STORE", "SHARE", "DISCARD", "COMPOST", "CONSENT"]],
        Field(max_length=10),
    ] = Field(default_factory=list)
    simulated: bool = True
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def require_expiry_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("expires_at must include a timezone")
        return value.astimezone(timezone.utc)


class IngredientReference(StrictModel):
    item_id: OpaqueId | None = None
    name: ItemName
    amount: Amount | None = None
    unit: UnitName | None = None
    uncertain: bool = False

    @model_validator(mode="after")
    def validate_quantity(self) -> IngredientReference:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        return self


class QuantityChange(StrictModel):
    item_id: OpaqueId | None = None
    name: ItemName
    original_amount: NonNegativeAmount | None = None
    proposed_amount: NonNegativeAmount | None = None
    unit: UnitName | None = None
    reason: Annotated[str, StringConstraints(max_length=300)]

    @model_validator(mode="after")
    def validate_quantity(self) -> QuantityChange:
        if self.unit is None and (self.original_amount is not None or self.proposed_amount is not None):
            raise ValueError("unit is required when a quantity is provided")
        return self


class MealSuggestionCard(ProposalBase):
    type: Literal["MealSuggestion"]
    title: ItemName
    servings: Annotated[StrictInt, Field(ge=1, le=100)]
    ingredients: Annotated[list[IngredientReference], Field(max_length=50)]


class PortionAdjustmentCard(ProposalBase):
    type: Literal["PortionAdjustment"]
    original_servings: Annotated[StrictInt, Field(ge=1, le=100)]
    proposed_servings: Annotated[StrictInt, Field(ge=1, le=100)]
    changes: Annotated[list[QuantityChange], Field(max_length=50)]
    # The agent output may omit this field; the API fills it from the verified plan.
    plan_title: ItemName | None = None


class BuyCheckCard(ProposalBase):
    type: Literal["BuyCheck"]
    item_name: ItemName
    stock_state: Literal["CONFIRMED", "STALE", "UNKNOWN", "NOT_FOUND"]
    shopping_action: Literal["ADD", "SKIP", "EDIT", "CONFIRM_STOCK"]


class FoodActionCard(ProposalBase):
    type: Literal["FoodAction"]
    item_id: OpaqueId
    action: Literal["USE", "STORE", "SHARE", "DISCARD", "COMPOST"]
    amount: Amount | None = None
    unit: UnitName | None = None

    @model_validator(mode="after")
    def validate_quantity(self) -> FoodActionCard:
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must be provided together")
        return self


class PreferenceConsentCard(ProposalBase):
    type: Literal["PreferenceConsent"]
    preference_key: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    proposed_text: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    requires_explicit_consent: Literal[True] = True


ProposalCard = Annotated[
    MealSuggestionCard | PortionAdjustmentCard | BuyCheckCard | FoodActionCard | PreferenceConsentCard,
    Field(discriminator="type"),
]


class AssistantEnvelope(StrictModel):
    schema_version: Literal[1] = 1
    request_id: str
    session_id: OpaqueId | None = None
    message: Annotated[str, StringConstraints(max_length=8_000)]
    cards: Annotated[list[ProposalCard], Field(max_length=20)] = Field(default_factory=list)


class AssistantTurnRequest(StrictModel):
    schema_version: Literal[1] = 1
    text: Annotated[str, StringConstraints(min_length=1, max_length=8_000)]
    session_id: OpaqueId | None = None
    context_item_ids: Annotated[list[OpaqueId], Field(max_length=50)] = Field(default_factory=list)
