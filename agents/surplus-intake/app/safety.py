"""Fail-closed runner-level input bounds for private intake media."""

from __future__ import annotations

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.genai import types

_SAFE_STATE_KEY = "ecoloop_input_safe"
_BLOCKED_MESSAGE = (
    "The intake could not be processed because its input was missing, unsupported, "
    "or too large."
)
_IMAGE_MIME_LIMITS = {
    "image/jpeg": 2_000_000,
    "image/png": 2_000_000,
    "image/webp": 2_000_000,
}
_AUDIO_MIME_LIMITS = {
    "audio/mpeg": 5_000_000,
    "audio/mp3": 5_000_000,
    "audio/mp4": 5_000_000,
    "audio/m4a": 5_000_000,
    "audio/ogg": 5_000_000,
    "audio/wav": 5_000_000,
    "audio/webm": 5_000_000,
}


class BoundedIntakeInputPlugin(BasePlugin):
    """Reject unsupported or oversized input before it reaches model history."""

    def __init__(self) -> None:
        super().__init__(name="bounded_intake_input")

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> types.Content | None:
        text_chars = 0
        media_parts = 0
        valid_parts = 0
        blocked = False

        for part in user_message.parts or []:
            if part.text:
                valid_parts += 1
                text_chars += len(part.text)
                continue
            blob = part.inline_data
            if blob is None:
                blocked = True
                continue
            valid_parts += 1
            media_parts += 1
            payload_size = len(blob.data or b"")
            mime_type = (blob.mime_type or "").lower()
            limit = _IMAGE_MIME_LIMITS.get(mime_type) or _AUDIO_MIME_LIMITS.get(
                mime_type
            )
            if limit is None or payload_size == 0 or payload_size > limit:
                blocked = True

        if valid_parts == 0 or text_chars > 8_000 or media_parts > 1:
            blocked = True

        invocation_context.session.state[_SAFE_STATE_KEY] = not blocked
        if not blocked:
            return None
        return types.Content(
            role="user",
            parts=[types.Part.from_text(text=_BLOCKED_MESSAGE)],
        )

    async def before_run_callback(
        self,
        *,
        invocation_context: InvocationContext,
    ) -> types.Content | None:
        if invocation_context.session.state.get(_SAFE_STATE_KEY, True):
            return None
        invocation_context.session.state[_SAFE_STATE_KEY] = True
        return types.Content(
            role="model",
            parts=[types.Part.from_text(text=_BLOCKED_MESSAGE)],
        )
