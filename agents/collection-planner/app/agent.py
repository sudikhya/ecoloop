"""EcoLoop advisory NGO collection-planning agent."""

import json

from google.adk.agents import Agent, SequentialAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from app.contracts import RouteProposalCandidate
from app.prompts import FORMATTER_INSTRUCTION, PLANNER_INSTRUCTION
from app.safety import CollectionSafetyPlugin
from app.tools import calculate_collection_route, list_confirmed_surplus

MODEL = "gemini-3.8-flash"


def _model() -> Gemini:
    return Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=2),
    )


planner = Agent(
    name="collection_tool_planner",
    model=_model(),
    instruction=PLANNER_INSTRUCTION,
    description=(
        "Selects compatible demo surplus and requests one bounded Google route."
    ),
    tools=[list_confirmed_surplus, calculate_collection_route],
    output_key="planning_draft",
    generate_content_config=types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=3_072,
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    ),
)

formatter = Agent(
    name="collection_proposal_formatter",
    model=_model(),
    instruction=FORMATTER_INSTRUCTION
    + "\n\nReturn only one JSON object matching the schema below. Do not wrap it in markdown.\n"
    + json.dumps(RouteProposalCandidate.model_json_schema(), separators=(",", ":")),
    description="Copies validated tool facts into a typed advisory proposal.",
    generate_content_config=types.GenerateContentConfig(
        temperature=0,
        max_output_tokens=4_096,
        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    ),
)

root_agent = SequentialAgent(
    name="collection_planner_agent",
    description=(
        "Creates a typed, non-binding collection route proposal for one NGO ask."
    ),
    sub_agents=[planner, formatter],
)

app = App(
    root_agent=root_agent,
    name="app",
    plugins=[CollectionSafetyPlugin()],
)
