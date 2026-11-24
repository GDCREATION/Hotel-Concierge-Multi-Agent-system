# Sunrise Hostel Concierge

Multi-agent lab for a fictional hostel. The guest is already logged in. An orchestrator talks to them and delegates to a booking specialist and a kitchen specialist. Specialists load tools from the in-repo MCP server.

## Stack

- Python 3.11+ (3.12 used in `.python-version`)
- LangGraph for the orchestrator graph, short-term memory, and `interrupt()` / `Command(resume=...)`
- FastMCP for the four business tools
- Pytest for allow-lists, approval, limits, and reference prompts
- Live model calls use Amazon Bedrock (`ChatBedrockConverse`, default Claude Haiku 4.5 in `us-east-1`). `HOSTEL_MODEL=scripted` is only for pytest and the checked-in traces.

## Non-negotiables

- The orchestrator has no booking or kitchen tools. Specialists are the tools.
- Each specialist receives only its allow-list from `config/safety.yaml`.
- `request_check_in_or_out` and `place_room_order` propose only. Writes happen in `booking_service.commit` and `kitchen_service.commit` after `grant_approval()`.
- Guest id and room come from `GuestContext` bound by the app. Strip them if a model puts them in tool args.
- A request that names another room is blocked in `scope.py` before any tool runs.
- Model-call and tool-call caps live in code. Hitting one returns a message that starts with `Stopped:`.
- Do not claim an action happened unless the specialist result status is `completed`.
- Mock data stays in `data/*.json`. Tests copy that directory; do not point tests at the repo copy.

## Layout

- `src/hostel_concierge/agents/orchestrator.py` — guest-facing graph
- `src/hostel_concierge/agents/specialist.py` — booking and kitchen loops
- `src/hostel_concierge/mcp_server/server.py` — four MCP tools
- `src/hostel_concierge/safety/` — allow-list, approval gate, limits
- `config/safety.yaml` — which tools pause, and the caps
- `docs/design-note.md` — the one-page design note
- `docs/stories/` — what each implementation story taught
- `traces/` — R1–R7 and the limit-stop demo

## Checks

```bash
PYTHONPATH=src .venv/bin/python -m pytest
PYTHONPATH=src .venv/bin/python -m hostel_concierge.trace_runner
PYTHONPATH=src .venv/bin/python -m hostel_concierge.demo_limit
```
