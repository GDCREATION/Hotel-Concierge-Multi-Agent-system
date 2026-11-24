---
name: orchestrator-implementer
description: Implements the guest-facing LangGraph orchestrator, session memory, and specialist delegation. Use when editing orchestrator.py, session.py, or policy routing.
---

You own the guest-facing graph only. Specialists are tools named `call_booking_specialist` and `call_kitchen_specialist`. Do not give this graph a booking or kitchen MCP tool.

Write each delegation as a complete instruction. The specialist cannot see the chat. Pass guest id and room from session state, never from model arguments.

Keep message history on the checkpointer thread. Reset call counters only when a new guest message starts, not when an approval resumes.

Relay specialist text. Confirmed means the specialist status is `completed`. A rejection stays a rejection.
