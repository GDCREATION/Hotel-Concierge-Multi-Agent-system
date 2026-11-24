# Sunrise Hostel Concierge

A logged-in guest talks only to an orchestrator. The orchestrator delegates to a booking specialist and a kitchen specialist. Those specialists call tools on a local MCP server. Risky tools pause until the guest approves, and that pause is enforced in code.

The hostel data is mock JSON. Room **305** (Asha Menon, `g-305`) is the demo guest. She is already checked in, with checkout on 2026-11-26. Room 101 is already checked out. Room 412 has not arrived.

## Stack

| Piece | Choice |
| --- | --- |
| Language | Python 3.12 |
| Orchestration | LangGraph (`interrupt` + checkpointer memory) |
| Tools | FastMCP, four tools, specialists are MCP clients |
| Model | Amazon Bedrock (`ChatBedrockConverse`). `scripted` for tests and traces |
| Tests | pytest |

Live turns call Amazon Bedrock through the standard AWS credential chain (environment, shared config, or SSO). The default model is Claude Haiku 4.5 (`us.anthropic.claude-haiku-4-5-20251001-v1:0` in `us-east-1`). Override it with `BEDROCK_MODEL_ID` and `AWS_REGION`. `HOSTEL_MODEL=scripted` skips Bedrock; pytest and `trace_runner` set that so the saved traces stay repeatable. Prompts live in `src/hostel_concierge/agents/prompts.py`.

Other stacks that can do this job, and why they are not the default here, are listed in the story plan: LangChain's older agent executor, CrewAI, AutoGen, AWS Bedrock supervisor agents, the Vercel AI SDK, the OpenAI Agents SDK, and Semantic Kernel. LangGraph is the one that already has a real pause/resume primitive for the approval requirement.

## Layout

```text
src/hostel_concierge/
  agents/orchestrator.py    guest-facing graph; specialists are tools
  agents/specialist.py      booking and kitchen loops, allow-lists applied
  mcp_server/server.py      the four MCP tools
  safety/                   allow-list, approval gate, call limits
  booking_service.py        reads and checkout/check-in proposals
  kitchen_service.py        menu, hours, order proposals
data/                       guests, menu, kitchen hours, orders
config/safety.yaml          approval tools, caps, allow-lists
traces/                     R1–R7 and the limit demo
docs/design-note.md         one-page design note
docs/stories/               what each story added
```

## Setup

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
export PYTHONPATH=src
```

Copy `.env.example` to `.env` if you want to pin the model id. The CLI loads it. Credentials come from AWS, not from that file.

## Run

```bash
# frozen breakfast service, room 305
HOSTEL_NOW=2026-11-24T08:30:00 PYTHONPATH=src .venv/bin/python -m hostel_concierge.cli --room 305

# Streamlit demo UI (Bedrock; room 305 bound in the app)
HOSTEL_NOW=2026-11-24T08:30:00 HOSTEL_MODEL=bedrock PYTHONPATH=src \
  .venv/bin/streamlit run src/hostel_concierge/ui/app.py

# reference traces
PYTHONPATH=src .venv/bin/python -m hostel_concierge.trace_runner

# looping model stopped by the cap
PYTHONPATH=src .venv/bin/python -m hostel_concierge.cli --demo-limit

# four MCP tools; proposals do not write JSON
PYTHONPATH=src .venv/bin/python -m hostel_concierge.mcp_smoke

PYTHONPATH=src .venv/bin/python -m pytest
```

A local-only walkthrough of every flow lives in `LOCAL_DEMO_RUNBOOK.md` (gitignored; not pushed).

In the CLI, approve with `y` and reject with `n`. Nothing is written until you approve. `/quit` leaves.

Cursor can also start the MCP server from `.cursor/mcp.json`. That process binds room 305 from the environment so the inspector can call tools. The guest chat does not use that shortcut: `Session.ask` passes the guest on every turn.

## What the system enforces

- **Delegation.** The orchestrator graph only has `call_booking_specialist` and `call_kitchen_specialist`.
- **Allow-lists.** `config/safety.yaml` intersected with the live MCP tool list. Kitchen cannot see a booking tool.
- **Approval.** Gated tools return a proposal. `grant_approval()` then `commit`. A missing token does not write.
- **Limits.** Each agent has a model-call cap and a per-tool cap. The stop message starts with `Stopped:`.
- **Memory.** One LangGraph thread keeps the messages. Follow-ups are rewritten as a full instruction because the specialist never sees the chat.
- **Identity.** `GuestContext` is the only room. A typed request for room 204 is blocked before tools run.

## Reference prompts

Saved under `traces/` for room 305 at 08:30 on 24 Nov 2026.

| Trace | Prompt |
| --- | --- |
| R1 | When is my checkout, and which room am I in? |
| R2 | Check me out tomorrow at 7 am. |
| R3 | Order a veg sandwich and a coffee to my room. |
| R4 | Is the kitchen open now? / and what's on the menu? |
| R5 | I check out at 7 am tomorrow, can I get breakfast ready? |
| R6 | Show me the booking for room 204. |
| R7 | What's the weather today? |

R5 asks for breakfast without naming a dish, so the kitchen reports hours and the menu instead of inventing an order. Checkout still waits for approval.

## Story notes

1. [Repo and Cursor workspace](docs/stories/01-scaffold.md)
2. [Mock data and guest context](docs/stories/02-data-and-context.md)
3. [MCP tools](docs/stories/03-mcp-tools.md)
4. [Safety layer](docs/stories/04-safety-layer.md)
5. [Booking specialist](docs/stories/05-booking-specialist.md)
6. [Kitchen specialist](docs/stories/06-kitchen-specialist.md)
7. [Orchestrator and CLI](docs/stories/07-orchestrator.md)
8. [Traces, design note, demo](docs/stories/08-deliverables.md)

The design note is [docs/design-note.md](docs/design-note.md). The 3–4 minute demo outline is [docs/demo-script.md](docs/demo-script.md).
