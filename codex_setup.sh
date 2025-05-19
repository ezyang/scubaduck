# This file is source'd by the codex agent and so any env vars it sets are
# available to the agent
uv venv -p 3.12
source .venv/bin/activate
uv sync
