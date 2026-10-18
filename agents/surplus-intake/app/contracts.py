"""Typed, candidate-only output for the EcoLoop surplus intake agent."""

from decimal import Decimal
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, model_validator

FoodCategory = Literal[
    "produce",
    "grains",
    "bakery",
    "dairy",
    "packaged",
    "prepared_food",
    "other",
]
FoodUnit = Literal["g", "kg", "ml", "l", "portion", "piece", "pack"]
PreparationState = Literal[
    "unprepared",
    "unserved_prepared",
    "packaged",
    "unknown",
]
PackagingState = Literal["sealed", "covered", "open", "unpackaged", "unknown"]
SourceModality = Literal["text", "image", "audio", "unknown"]
UnknownField = Literal[
    "food_name",
    "category",
    "amount",
    "unit",
    "preparation_state",
    "packaging_state",
]
ReviewFlag = Literal[
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


class SurplusCandidate(BaseModel):
    """One editable extraction candidate; never a confirmed surplus record."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    food_name: str | None = Field(default=None, min_length=1, max_length=100)
    category: FoodCategory | None = None
    amount: Decimal | None = None
    unit: FoodUnit | None = None
    preparation_state: PreparationState = "unknown"
    packaging_state: PackagingState = "unknown"
    unknown_fields: list[UnknownField] = Field(default_factory=list, max_length=6)
    review_flags: list[ReviewFlag] = Field(default_factory=list, max_length=9)
    disposition: Literal["review", "do_not_share"]
    evidence_note: str = Field(min_length=1, max_length=240)

    @model_validator(mode="after")
    def keep_amount_and_unit_together(self) -> "SurplusCandidate":
        if (self.amount is None) != (self.unit is None):
            raise ValueError("amount and unit must both be known or both be unknown")
        if self.amount is not None and (
            not self.amount.is_finite()
            or self.amount <= 0
            or len(self.amount.as_tuple().digits) > 10
            or max(-cast(int, self.amount.as_tuple().exponent), 0) > 3
        ):
            raise ValueError("amount must be positive with at most three decimals")
        return self


class SurplusIntakeOutput(BaseModel):
    """Bounded candidate list returned for household review."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_modality: SourceModality
    candidates: list[SurplusCandidate] = Field(max_length=12)
    summary: str = Field(min_length=1, max_length=300)
    requires_household_confirmation: bool = True
    safety_certified: bool = False
    demo_only: bool = True

    @model_validator(mode="after")
    def enforce_candidate_only_boundary(self) -> "SurplusIntakeOutput":
        if (
            self.requires_household_confirmation is not True
            or self.safety_certified is not False
            or self.demo_only is not True
        ):
            raise ValueError(
                "candidate-only safety fields must keep their fixed values"
            )
        return self
