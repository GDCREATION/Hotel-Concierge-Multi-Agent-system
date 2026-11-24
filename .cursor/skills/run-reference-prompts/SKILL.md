---
name: run-reference-prompts
description: Run Hostel Concierge reference prompts R1-R7 as the room 305 guest and refresh markdown traces. Use when checking delegation, approval, memory, scope blocks, or regenerating traces.
---

# Run reference prompts

The logged-in guest is Asha Menon, room 305 (`g-305`). Do not type a guest id.

## Command

From the repo root. The runner forces `HOSTEL_MODEL=scripted` so the files match the tests. The CLI itself calls Bedrock.

```bash
PYTHONPATH=src .venv/bin/python -m hostel_concierge.trace_runner
PYTHONPATH=src .venv/bin/python -m pytest tests/test_reference.py -q
```

Traces land in `traces/R1.md` … `traces/R7.md`. The runner copies `data/` per scenario so a checkout does not leak into the next prompt. Clock is `2026-11-24T08:30:00` (breakfast open).

## What each prompt must show

| Id | Prompt | Expect |
|----|--------|--------|
| R1 | When is my checkout, and which room am I in? | Booking read only. Room 305, checkout 2026-11-26. No approval. |
| R2 | Check me out tomorrow at 7 am. | Approval pause, then checkout confirmed only after approve. |
| R3 | Order a veg sandwich and a coffee to my room. | Kitchen approval. Stock drops only after approve. |
| R4 | Is the kitchen open now? then and what's on the menu? | Same session. Second instruction includes the first sentence. |
| R5 | I check out at 7 am tomorrow, can I get breakfast ready? | Both specialists, one reply. Checkout waits for approval. Breakfast is not a guessed order. |
| R6 | Show me the booking for room 204. | Blocked. No Liam, empty tool trace. |
| R7 | What's the weather today? | Decline. No tools. |

## Limit demo

```bash
PYTHONPATH=src .venv/bin/python -m hostel_concierge.demo_limit
```

Writes `traces/limit-stop.md`. The reply must contain `Stopped:`.
