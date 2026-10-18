"""Deterministic evaluator for advisory collection proposal output."""

from __future__ import annotations

import json
from typing import Any


def _response_text(instance: dict[str, Any]) -> str:
    response = instance.get("response") or {}
    parts = response.get("parts") if isinstance(response, dict) else None
    if not isinstance(parts, list):
        return ""
    return "".join(
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()


def _payload(instance: dict[str, Any]) -> dict[str, Any] | None:
    text = _response_text(instance)
    if text.startswith("```json") and text.endswith("```"):
        text = text[7:-3].strip()
    try:
        value = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def evaluate(instance: dict[str, Any]) -> dict[str, Any]:
    payload = _payload(instance)
    if payload is None:
        return {"score": 0, "explanation": "The final response was not a JSON object."}
    stops = payload.get("selected_stops")
    if (
        payload.get("advisory_only") is not True
        or payload.get("demo_only") is not True
        or not isinstance(stops, list)
        or len(stops) > 10
    ):
        return {
            "score": 0,
            "explanation": "The advisory proposal envelope was invalid.",
        }
    stop_ids = [
        stop.get("surplus_id")
        for stop in stops
        if isinstance(stop, dict) and isinstance(stop.get("surplus_id"), str)
    ]
    if len(stop_ids) != len(stops) or len(stop_ids) != len(set(stop_ids)):
        return {
            "score": 0,
            "explanation": "The proposal contained invalid or duplicate stops.",
        }
    expected_ids = instance.get("expected_stop_ids")
    if isinstance(expected_ids, list) and set(stop_ids) != set(expected_ids):
        return {
            "score": 0,
            "explanation": "The selected stops did not match deterministic matching.",
        }
    for field in ("matched_amount", "unmet_amount"):
        expected = instance.get(f"expected_{field}")
        if expected is not None and str(payload.get(field)) != str(expected):
            return {
                "score": 0,
                "explanation": f"The {field} did not match the expected amount.",
            }
    expected_status = instance.get("expected_route_status")
    if expected_status and payload.get("route_status") != expected_status:
        return {
            "score": 0,
            "explanation": "The route status was not honest for this case.",
        }
    route = payload.get("route")
    if route is not None:
        if not isinstance(route, dict) or route.get("ordered_surplus_ids") != stop_ids:
            return {
                "score": 0,
                "explanation": "Route facts did not preserve selected stop order.",
            }
        if (
            not isinstance(route.get("encoded_polyline"), str)
            or not route["encoded_polyline"]
        ):
            return {
                "score": 0,
                "explanation": "A ready route lacked provider geometry.",
            }
    elif payload.get("route_status") == "ready":
        return {
            "score": 0,
            "explanation": "The proposal claimed a ready route without route facts.",
        }
    return {
        "score": 1,
        "explanation": "The proposal preserved matching, route, and advisory boundaries.",
    }
