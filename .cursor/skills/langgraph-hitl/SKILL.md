---
name: langgraph-hitl
description: Pause and resume the Hostel Concierge graph for human approval. Use when editing interrupts, the CLI approve prompt, or specialist side effects.
---

# LangGraph approval

Approval is `interrupt()` inside `safety/approval.py`, which runs on the orchestrator's tool node because the specialist is called as a tool. The checkpointer is `InMemorySaver` in `build_app`.

## Flow

1. The gated MCP tool returns `pending_approval` and does not write.
2. `interrupt({agent, tool, proposal, message})` raises `GraphInterrupt` and `Session.ask` sees `__interrupt__`.
3. The CLI or the trace runner sends `Command(resume={"approved": True/False})`.
4. The tool node restarts. `interrupt()` returns the decision instead of pausing.
5. Approve calls `grant_approval(proposal_id)` then the service `commit`. Reject returns status `rejected` and does not commit.

## Rules

- Do not write data before `interrupt()` returns an approval. The node restarts, so a write before the interrupt would run twice or run before the guest decides.
- Do not catch `GraphInterrupt` in a broad `except Exception`.
- New guest turns reset `orch_model_calls` and `orch_tool_counts` in `Session.ask`. Resume must not reset them.
- Every new turn passes `guest_id` and `room` from the session. The model has no channel for those fields.
- A missing decision in a non-interactive run is an error. Do not default to approve.

## Try it

```bash
HOSTEL_NOW=2026-11-24T08:30:00 PYTHONPATH=src .venv/bin/python -m hostel_concierge.cli --room 305
```

Ask to check out or to order. Answer `n` and confirm the reply says nothing changed.
