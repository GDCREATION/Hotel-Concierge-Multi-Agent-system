# Design note

## Why two specialists

One agent with every tool would still answer the guest, but it would also be the only place that can touch bookings and the kitchen. That makes the allow-list requirement decorative: the same model that talks to the guest would be holding `place_room_order` and `get_my_booking` at once. Splitting the work gives each specialist a tool list it cannot widen, and it gives the orchestrator a single place to remember the chat.

The guest only talks to the graph in `agents/orchestrator.py`. Delegation is the tool node there: `call_booking_specialist` and `call_kitchen_specialist` call `run_specialist`. The scripted model decides which of those to emit in `agents/policy.py`; a live model does the same choice with `ORCHESTRATOR_PROMPT` and those two schemas. Specialists never receive the message list. They get one instruction string built by `instruction_for`, which is why a follow-up such as "and what's on the menu?" still works: the orchestrator copies the earlier turn into that brief.

One agent would have been enough for a toy chatbot. It would not have been enough for this assignment, because the assignment grades the boundary: who may call which tool, and who is allowed to remember the conversation.

## Approval and tool access in code

The system prompt asks the model to be careful. That is not the control. Three checks sit in front of any write.

Tool access: `visible_tools` keeps the intersection of the MCP catalog and `config/safety.yaml`. `run_gated_or_direct` refuses a name that is not on that agent's list, which is what `tests/test_scope_and_safety.py` locks in. Commit functions are not MCP tools at all.

Approval: `request_check_in_or_out` and `place_room_order` only store a proposal. `interrupt()` in `safety/approval.py` pauses the orchestrator, because the specialist runs inside the orchestrator tool node and the graph has a checkpointer. Resume is `Command(resume={"approved": ...})` from `Session.ask`. Only an approval calls `grant_approval`, and `booking_service.commit` / `kitchen_service.commit` return `approval_missing` without that token. The node restarts after a pause, so the preview must not write; otherwise the replay would double-apply.

Identity: `Session.ask` writes `guest_id` and `room` from the app on every turn. Tool schemas have neither field. `strip_identity` drops them if a model adds them anyway. `scope.other_rooms` blocks a named room that is not the bound one before a tool runs, which is the room 204 case.

Limits use the same idea. The orchestrator counts in graph state. Each specialist has a `CallLimiter`. Either one stops with a `Stopped:` message instead of another model call.

## How the hard cases were tested

`tests/test_domain.py` covers the closed kitchen, zero stock, a checked-out guest, and a guest who has not arrived, plus commit-without-approval. `tests/test_mcp.py` calls the four tools through the MCP client and checks the files stay unchanged. `tests/test_reference.py` runs R1–R7 on the graph: R2 and R3 assert the pause and the write after approve, R4 asserts both user turns are still in state and the second instruction quotes the first, R5 asserts both specialist tools in one turn, R6 asserts a block with an empty tool trace and no mention of the other guest, R7 asserts no tool calls. `tests/test_agents.py` also rejects a checkout and runs a model that calls `get_my_booking` forever until the cap fires. The saved transcripts are `traces/R1.md`–`traces/R7.md` and `traces/limit-stop.md`.
