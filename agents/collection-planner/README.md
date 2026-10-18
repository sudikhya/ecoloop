# collection-planner

Advisory NGO food-surplus collection-planning agent
Agent generated with `agents-cli` version `1.10.0`

## Project Structure

```
collection-planner/
├── app/         # Core agent code
│   ├── agent.py               # Main agent logic
│   ├── fast_api_app.py        # FastAPI Backend server
│   └── app_utils/             # App utilities and helpers
├── tests/eval/                # Bounded synthetic agent evaluation
├── AGENTS.md                  # AI-assisted development guide
└── pyproject.toml             # Project dependencies
```

> 💡 **Tip:** Use [Antigravity CLI](https://antigravity.google/) for AI-assisted development - project context is pre-configured in `GEMINI.md`.

## Requirements

Before you begin, ensure you have:
- **uv**: Python package manager (used for all dependency management in this project) - [Install](https://docs.astral.sh/uv/getting-started/installation/) ([add packages](https://docs.astral.sh/uv/concepts/dependencies/) with `uv add <package>`)
- **agents-cli**: Agents CLI - Install with `uv tool install google-agents-cli`
- **Google Cloud SDK**: For GCP services - [Install](https://cloud.google.com/sdk/docs/install)


## Quick Start

Install `agents-cli` and its skills if not already installed:

```bash
uvx google-agents-cli setup
```

Install required packages:

```bash
agents-cli install
```

Test the agent with a local web server:

```bash
agents-cli playground
```

You can also use features from the [ADK](https://adk.dev/) CLI with `uv run adk`.

## Commands

| Command              | Description                                                                                 |
| -------------------- | ------------------------------------------------------------------------------------------- |
| `agents-cli install` | Install dependencies using uv                                                         |
| `agents-cli playground` | Launch local development environment                                                  |
| `agents-cli lint`    | Run code quality checks                                                               |
| `agents-cli eval`    | Evaluate agent behavior (generate, grade, analyze, and more — see `agents-cli eval --help`) |
| `uv run python -m compileall app` | Compile the agent application                                                   |
| [A2A Inspector](https://github.com/a2aproject/a2a-inspector) | Launch A2A Protocol Inspector                         |

## Development

Edit your agent logic in `app/agent.py` and test with `agents-cli playground` - it auto-reloads on save.

## Deployment

Deployment is intentionally owner-gated. Use the direct Agent Runtime path only
after billing verification, bounded evaluation, IAM/API/quota review, and fresh
approval. Do not add the scaffolded Terraform telemetry stack for this pilot.

```bash
agents-cli deploy \
  --project ecoloop-511918 \
  --region asia-south1 \
  --agent-identity \
  --memory 4Gi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 2 \
  --service-name ecoloop-collection-planner \
  --env-vars GOOGLE_GENAI_USE_ENTERPRISE=true,GOOGLE_CLOUD_LOCATION=global \
  --labels app=ecoloop,component=collection-planner,environment=demo
```

Agents CLI copies a project `.env` into the runtime environment. Perform the
approved deployment from a sanitized copy that excludes the real `.env`, as was
done for the dry-run; never print, commit, or upload that file.

## Observability

Keep prompt/response content capture off. Use bounded metadata-only Cloud
Logging/Monitoring after its separate privacy review; this pilot does not create
BigQuery or GCS telemetry stores.

## A2A Inspector

This agent supports the [A2A Protocol](https://a2a-protocol.org/). Use the [A2A Inspector](https://github.com/a2aproject/a2a-inspector) to test interoperability.
See the [A2A Inspector docs](https://github.com/a2aproject/a2a-inspector) for details.
