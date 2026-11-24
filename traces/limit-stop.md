# Limit stop

A looping model keeps requesting the same tool. The cap in config/code stops it.

## Specialist tool limit

Booking specialist, max 2 calls to `get_my_booking`.

{"specialist": "booking", "status": "limit", "message": "Stopped: booking reached the tool-call limit for get_my_booking (2 per request).", "tool_trace": [{"tool": "get_my_booking", "status": "ok", "steps": ["get_my_booking"]}, {"tool": "get_my_booking", "status": "ok", "steps": ["get_my_booking"]}]}

## Orchestrator tool and model limit

Orchestrator max_tool_calls=1 for each specialist tool, max_model_calls=3.

Stopped: orchestrator reached the model-call limit (3 per request).

# Limit stop — orchestrator loop

Logged-in guest: room 305. The guest did not type an id.
Clock: 2026-11-24T08:30:00

## Turn 1

**Guest:** Please keep checking.

### Delegations and specialist tools

- `call_booking_specialist`

```text
When is my checkout, and which room am I in?
```

- Result from `call_booking_specialist`

  - status: `ok`
  - tools: get_my_booking (ok)

- `call_booking_specialist`

```text
When is my checkout, and which room am I in?
```

- Result from `call_booking_specialist`

Stopped: orchestrator reached the tool-call limit for call_booking_specialist (1 per request).

- `call_booking_specialist`

```text
When is my checkout, and which room am I in?
```

- Result from `call_booking_specialist`

Stopped: orchestrator reached the tool-call limit for call_booking_specialist (1 per request).

### Reply

Stopped: orchestrator reached the model-call limit (3 per request).

## Session messages after the last turn

- guest: Please keep checking.
- orchestrator: call_booking_specialist
- tool:call_booking_specialist: {"specialist": "booking", "status": "ok", "message": "You are in room 305. Check-in 2026-11-20, checkout 2026-11-26, status checked-in.", "tool_trace": [{"tool": "get_my_booking", "status": "ok", "steps": ["get_my_booking"]}]}
- orchestrator: call_booking_specialist
- tool:call_booking_specialist: Stopped: orchestrator reached the tool-call limit for call_booking_specialist (1 per request).
- orchestrator: call_booking_specialist
- tool:call_booking_specialist: Stopped: orchestrator reached the tool-call limit for call_booking_specialist (1 per request).
- orchestrator: Stopped: orchestrator reached the model-call limit (3 per request).
