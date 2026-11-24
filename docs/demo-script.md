# Demo script (about 4 minutes)

Record the terminal. The CLI calls Amazon Bedrock (Claude Haiku 4.5 unless `BEDROCK_MODEL_ID` is set). Wording can differ from the saved `traces/`, which were generated with `HOSTEL_MODEL=scripted`.

```bash
export PYTHONPATH=src
export HOSTEL_NOW=2026-11-24T08:30:00
export HOSTEL_MODEL=bedrock
export AWS_REGION=us-east-1
.venv/bin/python -m hostel_concierge.cli --room 305
```

## 1. Order with approval (R3) — about 90 seconds

Type: `Order a veg sandwich and a coffee to my room.`

Show the approval panel: room 305, both items, "Nothing has been sent to the kitchen yet." Approve with `y`.

Point at the reply: it says the order is confirmed only after the specialist commit. If you have time, run it again in a second terminal and answer `n`, and show that the reply says nothing was changed.

## 2. Both specialists (R5) — about 90 seconds

In the same session, type: `I check out at 7 am tomorrow, can I get breakfast ready?`

The pause is only the checkout. Approve it. The single reply should confirm checkout and say the kitchen is open for breakfast, with the menu. Say out loud that breakfast was not guessed as a specific dish, and that both specialists were called (booking tool, then kitchen tool). `traces/R5.md` is the same shape if the recording is easier from the file.

## 3. A limit stops a loop — about 60 seconds

Quit, then:

```bash
.venv/bin/python -m hostel_concierge.cli --demo-limit
```

Show the line `Stopped: orchestrator reached the tool-call limit for call_booking_specialist` and the final `Stopped: orchestrator reached the model-call limit`. The looping model never decides to stop; the counter does.
