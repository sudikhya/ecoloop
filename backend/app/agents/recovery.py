from __future__ import annotations

import asyncio
import hashlib
import json
import re
from typing import Any, TypeVar

from google.genai import types
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.errors import DomainError
from app.domain.ai_usage import claim_daily_ai_request
from app.schemas.surplus import RouteProposalCandidate, SurplusIntakeResult

T = TypeVar("T", bound=BaseModel)
_IMAGE_SIGNATURES = {
    "image/jpeg": lambda value: value.startswith(b"\xff\xd8\xff"),
    "image/png": lambda value: value.startswith(b"\x89PNG\r\n\x1a\n"),
    "image/webp": lambda value: (
        len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WEBP"
    ),
}
_AUDIO_SIGNATURES = {
    "audio/mpeg": lambda value: (
        value.startswith(b"ID3") or (len(value) >= 2 and value[0] == 0xFF)
    ),
    "audio/mp3": lambda value: (
        value.startswith(b"ID3") or (len(value) >= 2 and value[0] == 0xFF)
    ),
    "audio/wav": lambda value: (
        len(value) >= 12 and value[:4] == b"RIFF" and value[8:12] == b"WAVE"
    ),
    "audio/ogg": lambda value: value.startswith(b"OggS"),
    "audio/webm": lambda value: value.startswith(b"\x1aE\xdf\xa3"),
    "audio/mp4": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
    "audio/m4a": lambda value: len(value) >= 12 and value[4:8] == b"ftyp",
}


def _resource(value: str | None, label: str) -> str:
    project = (
        settings.GOOGLE_CLOUD_PROJECT or settings.FIREBASE_PROJECT_ID or ""
    ).strip()
    location = settings.AGENT_RUNTIME_LOCATION.strip()
    resource = (value or "").strip()
    pattern = (
        rf"^projects/{re.escape(project)}/locations/{re.escape(location)}"
        r"/reasoningEngines/[^/]+$"
    )
    if (
        not settings.SURPLUS_PILOT_ENABLED
        or not project
        or not location
        or re.fullmatch(pattern, resource) is None
    ):
        raise DomainError(
            "RECOVERY_AGENT_UNAVAILABLE",
            f"The {label} agent is not configured.",
            503,
            retryable=True,
        )
    return resource


def _event_text(event: Any) -> str | None:
    if not isinstance(event, dict):
        return None
    content = event.get("content")
    if not isinstance(content, dict):
        return None
    parts = content.get("parts")
    if not isinstance(parts, list):
        return None
    values = [
        part.get("text")
        for part in parts
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ]
    value = "".join(values).strip()
    return value or None


def _json_payload(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```json") and stripped.endswith("```"):
        return stripped[7:-3].strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        return stripped[3:-3].strip()
    return stripped


def _validated_result(
    texts: list[str], output_type: type[T], invalid_code: str, invalid_message: str
) -> T:
    candidates = list(reversed(texts))
    if len(texts) > 1:
        candidates.append("".join(texts))
    for text in candidates:
        try:
            return output_type.model_validate_json(_json_payload(text))
        except (ValidationError, ValueError, json.JSONDecodeError):
            continue
    raise DomainError(invalid_code, invalid_message, 502, retryable=True)


async def _invoke_runtime(
    resource: str, message: dict[str, Any], actor_uid: str
) -> list[str]:
    try:
        import agentplatform

        project = (
            settings.GOOGLE_CLOUD_PROJECT or settings.FIREBASE_PROJECT_ID or ""
        ).strip()
        client = agentplatform.Client(
            project=project, location=settings.AGENT_RUNTIME_LOCATION
        )
        runtime = client.runtimes.get(name=resource)
        texts: list[str] = []
        async with asyncio.timeout(settings.SURPLUS_AGENT_TIMEOUT_SECONDS):
            async for event in runtime.async_stream_query(
                message=message,
                user_id=hashlib.sha256(actor_uid.encode("utf-8")).hexdigest(),
                session_events=[],
            ):
                value = _event_text(event)
                if value:
                    texts.append(value)
        return texts
    except DomainError:
        raise
    except Exception as exc:
        raise DomainError(
            "RECOVERY_AGENT_UNAVAILABLE",
            "The recovery agent could not complete this request.",
            503,
            retryable=True,
        ) from exc


async def extract_surplus_text(uid: str, text: str) -> dict[str, Any]:
    resource = _resource(settings.SURPLUS_INTAKE_AGENT_RESOURCE, "surplus intake")
    claim_daily_ai_request(uid)
    payload = json.dumps(
        {"source_modality": "text", "household_input": text},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    content = types.Content(role="user", parts=[types.Part.from_text(text=payload)])
    texts = await _invoke_runtime(
        resource,
        content.model_dump(mode="json", by_alias=True, exclude_none=True),
        uid,
    )
    result = _validated_result(
        texts,
        SurplusIntakeResult,
        "SURPLUS_EXTRACTION_INVALID",
        "The intake agent returned an invalid candidate. Enter the surplus manually.",
    )
    return result.model_dump(mode="json")


def validate_surplus_media(media: bytes, mime_type: str) -> str:
    if not media:
        raise DomainError(
            "EMPTY_MEDIA", "Choose a non-empty image or audio recording.", 422
        )
    if len(media) > settings.MAX_SURPLUS_MEDIA_BYTES:
        raise DomainError(
            "PAYLOAD_TOO_LARGE", "The surplus media exceeds the supported size.", 413
        )
    normalized = mime_type.split(";", 1)[0].strip().lower()
    signature = _IMAGE_SIGNATURES.get(normalized) or _AUDIO_SIGNATURES.get(normalized)
    if signature is None or not signature(media):
        raise DomainError(
            "UNSUPPORTED_MEDIA",
            "Choose a supported JPEG, PNG, WebP, MP3, M4A, WAV, Ogg, or WebM file.",
            422,
        )
    return "image" if normalized in _IMAGE_SIGNATURES else "audio"


async def extract_surplus_media(
    uid: str, media: bytes, mime_type: str
) -> dict[str, Any]:
    modality = validate_surplus_media(media, mime_type)
    resource = _resource(settings.SURPLUS_INTAKE_AGENT_RESOURCE, "surplus intake")
    claim_daily_ai_request(uid)
    content = types.Content(
        role="user",
        parts=[
            types.Part.from_text(
                text=f"Source modality: {modality}. Extract editable candidates only."
            ),
            types.Part.from_bytes(
                data=media, mime_type=mime_type.split(";", 1)[0].strip().lower()
            ),
        ],
    )
    texts = await _invoke_runtime(
        resource,
        content.model_dump(mode="json", by_alias=True, exclude_none=True),
        uid,
    )
    result = _validated_result(
        texts,
        SurplusIntakeResult,
        "SURPLUS_EXTRACTION_INVALID",
        "The intake agent returned an invalid candidate. Enter the surplus manually.",
    )
    if result.source_modality not in {modality, "unknown"}:
        raise DomainError(
            "SURPLUS_EXTRACTION_INVALID",
            "The intake agent returned an inconsistent source type. "
            "Enter the surplus manually.",
            502,
            retryable=True,
        )
    return result.model_dump(mode="json")


async def propose_collection_route(
    uid: str,
    request_record: dict[str, Any],
    surplus_records: list[dict[str, Any]],
) -> RouteProposalCandidate:
    resource = _resource(
        settings.COLLECTION_PLANNER_AGENT_RESOURCE, "collection planning"
    )
    claim_daily_ai_request(uid)
    payload = json.dumps(
        {
            "verified_request": request_record,
            "confirmed_surplus": surplus_records[:100],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    content = types.Content(role="user", parts=[types.Part.from_text(text=payload)])
    texts = await _invoke_runtime(
        resource,
        content.model_dump(mode="json", by_alias=True, exclude_none=True),
        uid,
    )
    return _validated_result(
        texts,
        RouteProposalCandidate,
        "COLLECTION_PROPOSAL_INVALID",
        "The collection planner returned an invalid proposal.",
    )
