# Streamlit demo UI design

## Goal

Internal Streamlit panel that demonstrates the full Hostel Concierge flow: free-form guest chat, reference scenarios R1–R7, approval pauses, turn inspection (specialists + tools), and the limit-stop demo. Bedrock only. A local gitignored runbook explains how to start and walk each flow.

## Architecture

- One Streamlit process; MCP stays in-process via the existing FastMCP client (same as the CLI).
- Guest is bound as room 305 through `GuestContext`. The UI never asks for guest id or room.
- `Session` gains non-blocking pause/resume so Streamlit can show Approve/Reject without Rich `input()`.
- Existing `Session.ask` remains for the CLI and tests.

## Session API

| Method | Behavior |
| --- | --- |
| `ask_until_interrupt(text)` | Invoke the graph. On `__interrupt__`, return `TurnResult(pending=True, approvals=[payload], reply="")`. Otherwise return the final reply. |
| `resume(approved, prior_approvals=…)` | `Command(resume={"approved": …})`. Same return shape; may pause again or finish. |
| `ask(...)` | Loops using the above + `decision_source` / interactive Rich prompt. |

`TurnResult` adds `pending: bool`.

## UI

- **Sidebar:** room 305 badge, R1–R7 + Limit stop buttons, Reset session, short expectation text for the selected scenario.
- **Main:** chat transcript; approval card when `pending`; turn inspector (specialists, tools, pending proposal).
- **Model:** Bedrock (`HOSTEL_MODEL=bedrock`). AWS credentials required.
- **Errors:** Bedrock/AWS failures as banners; scope blocks and `Stopped:` as normal replies.

## Local runbook (not pushed)

- File: `LOCAL_DEMO_RUNBOOK.md` (root)
- Listed in `.gitignore`
- Covers setup, Streamlit start, optional CLI/mcp_smoke, and each flow

## Out of scope

Gradio, scripted-model toggle, FastAPI, CLI redesign, safety-rule changes.
