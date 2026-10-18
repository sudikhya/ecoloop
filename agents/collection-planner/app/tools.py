"""Narrow, read-only planning tools. They never mutate EcoLoop records."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import google.auth
from google.auth.transport.requests import AuthorizedSession
from pydantic import TypeAdapter, ValidationError

from app.contracts import (
    ConfirmedSurplusOption,
    Location,
    NgoRequestPayload,
    SelectedStop,
)

_SURPLUS_LIST = TypeAdapter(list[ConfirmedSurplusOption])
_STOP_LIST = TypeAdapter(list[SelectedStop])
_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def _decimal_text(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _food_matches(
    request: NgoRequestPayload,
    option: ConfirmedSurplusOption,
) -> bool:
    requested_name = (request.food_name or "").casefold()
    exact_name = bool(requested_name) and option.food_name.casefold() == requested_name
    category_match = (
        request.category is not None and option.category == request.category
    )
    if request.food_name is not None and request.category is not None:
        return exact_name and category_match
    return exact_name if request.food_name is not None else category_match


def list_confirmed_surplus(request_json: str, surplus_json: str) -> dict[str, Any]:
    """Validate a server-supplied eligible snapshot and select at most ten stops.

    Args:
        request_json: JSON for one verified NGO request and its origin.
        surplus_json: JSON array projected by FastAPI from confirmed pilot surplus.

    Returns:
        A bounded shortlist with compatible pickup amounts and explicit unmet amount.
    """
    try:
        request = NgoRequestPayload.model_validate_json(request_json)
        options = _SURPLUS_LIST.validate_json(surplus_json)
    except ValidationError:
        return {"status": "invalid_input"}

    now = datetime.now(UTC)
    compatible = [
        option
        for option in options[:100]
        if option.unit == request.unit
        and option.available_until > now
        and _food_matches(request, option)
    ]
    compatible.sort(
        key=lambda option: (
            -option.amount,
            option.available_until,
            option.surplus_id,
        )
    )

    remaining = request.amount
    selected: list[SelectedStop] = []
    for option in compatible:
        if remaining <= 0 or len(selected) >= 10:
            break
        pickup_amount = min(option.amount, remaining)
        selected.append(
            SelectedStop(
                surplus_id=option.surplus_id,
                version=option.version,
                household_id=option.household_id,
                food_name=option.food_name,
                pickup_amount=pickup_amount,
                unit=option.unit,
                available_until=option.available_until,
                location=option.location,
            )
        )
        remaining -= pickup_amount

    matched = request.amount - remaining
    return {
        "status": "ok",
        "request_id": request.request_id,
        "origin": request.origin.model_dump(mode="json"),
        "selected_stops": [stop.model_dump(mode="json") for stop in selected],
        "matched_amount": _decimal_text(matched),
        "unmet_amount": _decimal_text(max(remaining, Decimal("0"))),
        "unit": request.unit,
        "selection_rule": "largest_compatible_amount_first_then_earliest_deadline",
    }


def _waypoint(location: Location) -> dict[str, Any]:
    return {
        "location": {
            "latLng": {
                "latitude": location.latitude,
                "longitude": location.longitude,
            }
        }
    }


def _duration_seconds(value: str) -> int:
    if not value.endswith("s"):
        raise ValueError("unexpected duration")
    return max(0, int(Decimal(value[:-1])))


def calculate_collection_route(
    origin_json: str,
    selected_stops_json: str,
) -> dict[str, Any]:
    """Request one bounded driving route from Google Maps Routes API.

    Args:
        origin_json: JSON location for the verified NGO starting point.
        selected_stops_json: JSON array of one to ten validated selected stops.

    Returns:
        Google route distance, duration, encoded polyline and optimized stop order.
    """
    try:
        origin = Location.model_validate_json(origin_json)
        stops = _STOP_LIST.validate_json(selected_stops_json)
    except ValidationError:
        return {"status": "invalid_input"}
    if not 1 <= len(stops) <= 10:
        return {"status": "invalid_stop_count"}

    payload = {
        "origin": _waypoint(origin),
        "destination": _waypoint(origin),
        "intermediates": [_waypoint(stop.location) for stop in stops],
        "travelMode": "DRIVE",
        "computeAlternativeRoutes": False,
        "optimizeWaypointOrder": True,
        "languageCode": "en-IN",
        "units": "METRIC",
    }
    field_mask = ",".join(
        (
            "routes.distanceMeters",
            "routes.duration",
            "routes.polyline.encodedPolyline",
            "routes.optimizedIntermediateWaypointIndex",
            "routes.legs.distanceMeters",
            "routes.legs.duration",
        )
    )

    try:
        credentials, detected_project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        billing_project = os.getenv("GOOGLE_CLOUD_PROJECT") or detected_project
        headers = {
            "Content-Type": "application/json",
            "X-Goog-FieldMask": field_mask,
        }
        if billing_project:
            headers["X-Goog-User-Project"] = billing_project
        response = AuthorizedSession(credentials).post(
            _ROUTES_URL,
            json=payload,
            headers=headers,
            timeout=12,
        )
        response.raise_for_status()
        body = response.json()
        route = body["routes"][0]
        polyline = route["polyline"]["encodedPolyline"]
        distance_meters = int(route["distanceMeters"])
        duration_seconds = _duration_seconds(route["duration"])
        optimized_indices = route["optimizedIntermediateWaypointIndex"]
        if sorted(optimized_indices) != list(range(len(stops))):
            raise ValueError("invalid optimized stop order")
        ordered_stops = [stops[index] for index in optimized_indices]
        if not polyline or distance_meters < 0 or duration_seconds < 0:
            raise ValueError("invalid route values")
    except Exception:
        return {"status": "unavailable"}

    return {
        "status": "ok",
        "distance_meters": distance_meters,
        "duration_seconds": duration_seconds,
        "encoded_polyline": polyline,
        "ordered_surplus_ids": [stop.surplus_id for stop in ordered_stops],
        "ordered_stops": [stop.model_dump(mode="json") for stop in ordered_stops],
    }
