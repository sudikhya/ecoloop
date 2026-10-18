"""Runner-level input and tool guards for the collection planner."""

from __future__ import annotations

import json
from typing import Any

from google.adk.agents.invocation_context import InvocationContext
from google.adk.plugins.base_plugin import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

_SAFE_STATE_KEY = "ecoloop_input_safe"
_TOOL_PHASE_STATE_KEY = "ecoloop_collection_tool_phase"
_BLOCKED_MESSAGE = (
    "The collection request was rejected because its input was missing, unsupported, "
    "or too large."
)
_ALLOWED_TOOLS = frozenset({"list_confirmed_surplus", "calculate_collection_route"})


class CollectionSafetyPlugin(BasePlugin):
    """Keep invocation text bounded and fail closed around the two read-only tools."""

    def __init__(self) -> None:
        super().__init__(name="collection_safety")

    async def on_user_message_callback(
        self,
        *,
        invocation_context: InvocationContext,
        user_message: types.Content,
    ) -> types.Content | None:
        total_chars = 0
        blocked = False
        for part in user_message.parts or []:
            if part.text is None:
                blocked = True
                continue
            total_chars += len(part.text)
        if total_chars == 0 or total_chars > 96_000:
            blocked = True
        invocation_context.session.state[_SAFE_STATE_KEY] = not blocked
        invocation_context.session.state[_TOOL_PHASE_STATE_KEY] = (
            "blocked" if blocked else "start"
        )
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

    async def before_tool_callback(
        self,
        *,
        tool: BaseTool,
        tool_args: dict[str, Any],
        tool_context: ToolContext,
    ) -> dict[str, Any] | None:
        if tool.name not in _ALLOWED_TOOLS:
            return {"status": "blocked", "reason": "tool_not_allowed"}
        phase = tool_context.state.get(_TOOL_PHASE_STATE_KEY)
        expected_phase = {
            "list_confirmed_surplus": "start",
            "calculate_collection_route": "listed",
        }[tool.name]
        if phase != expected_phase:
            return {"status": "blocked", "reason": "unexpected_tool_order"}
        try:
            encoded = json.dumps(tool_args, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError):
            return {"status": "blocked", "reason": "invalid_tool_arguments"}
        if len(encoded) > 96_000:
            return {"status": "blocked", "reason": "tool_arguments_too_large"}
        tool_context.state[_TOOL_PHASE_STATE_KEY] = (
            "listed" if tool.name == "list_confirmed_surplus" else "routed"
        )
        return None
