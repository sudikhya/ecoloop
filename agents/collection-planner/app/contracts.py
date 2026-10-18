"""Typed inputs and advisory output for EcoLoop collection planning."""

from __future__ import annotations

from datetime import datetime
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


class Location(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    address: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    place_id: str | None = Field(default=None, max_length=300)


class NgoRequestPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    food_name: str | None = Field(default=None, min_length=1, max_length=100)
    category: FoodCategory | None = None
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: FoodUnit
    origin: Location


class ConfirmedSurplusOption(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    surplus_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    version: int = Field(ge=1)
    household_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    status: Literal["CONFIRMED"]
    food_name: str = Field(min_length=1, max_length=100)
    category: FoodCategory
    amount: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    unit: FoodUnit
    available_until: datetime
    location: Location
    eligible: Literal[True]
    demo_only: Literal[True]


class SelectedStop(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    surplus_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    version: int = Field(ge=1)
    household_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    food_name: str = Field(min_length=1, max_length=100)
    pickup_amount: Decimal
    unit: FoodUnit
    available_until: datetime
    location: Location

    @model_validator(mode="after")
    def validate_pickup_amount(self) -> SelectedStop:
        if (
            not self.pickup_amount.is_finite()
            or self.pickup_amount <= 0
            or len(self.pickup_amount.as_tuple().digits) > 10
            or max(-cast(int, self.pickup_amount.as_tuple().exponent), 0) > 3
        ):
            raise ValueError(
                "pickup_amount must be positive with at most three decimals"
            )
        return self


class RouteFacts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    distance_meters: int = Field(ge=0)
    duration_seconds: int = Field(ge=0)
    encoded_polyline: str = Field(min_length=1, max_length=200_000)
    ordered_surplus_ids: list[str] = Field(min_length=1, max_length=10)


class RouteProposalCandidate(BaseModel):
    """Non-binding proposal. FastAPI revalidates it before persistence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    selected_stops: list[SelectedStop] = Field(max_length=10)
    matched_amount: Decimal
    unmet_amount: Decimal
    unit: FoodUnit
    route_status: Literal["ready", "unavailable", "no_matches"]
    route: RouteFacts | None = None
    explanation: str = Field(min_length=1, max_length=600)
    warnings: list[str] = Field(default_factory=list, max_length=8)
    advisory_only: bool = True
    demo_only: bool = True

    @model_validator(mode="after")
    def enforce_advisory_boundary(self) -> RouteProposalCandidate:
        if self.advisory_only is not True or self.demo_only is not True:
            raise ValueError("proposal boundary fields must keep their fixed values")
        for name, value in (
            ("matched_amount", self.matched_amount),
            ("unmet_amount", self.unmet_amount),
        ):
            if (
                not value.is_finite()
                or value < 0
                or len(value.as_tuple().digits) > 10
                or max(-cast(int, value.as_tuple().exponent), 0) > 3
            ):
                raise ValueError(
                    f"{name} must be non-negative with at most three decimals"
                )
        return self
