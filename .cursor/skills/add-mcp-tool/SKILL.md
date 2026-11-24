---
name: add-mcp-tool
description: Add a Hostel Concierge MCP tool and decide whether it is a plain read or an approval-gated proposal. Use when adding or changing a booking or kitchen tool.
---

# Add an MCP tool

Tools live in `src/hostel_concierge/mcp_server/server.py`. Business rules live in `booking_service.py` or `kitchen_service.py`. The model must not be able to write files by calling the tool.

## Checklist

1. Put the read or the proposal in the service. Return `{status, message}` for not-found, closed, out of stock, and invalid status. Do not raise those cases.
2. Register an MCP tool with `run_in_thread=False` so it sees the guest bound on the caller thread.
3. Do not add `guest_id` or `room` parameters. Call `require_guest()`.
4. If the tool changes a booking or sends an order, it must only save a proposal (`pending_approval`) and leave JSON unchanged.
5. Add the commit function next to the service and call it only from `safety/approval.py` after `grant_approval()`.
6. Add the tool name to the right list in `config/safety.yaml`. If it pauses, also add it under `approval_required_tools`.
7. Add a LangChain schema tool in `agents/specialist.py` so a live model can see the name and arguments. Execution still goes through `run_gated_or_direct`.
8. Extend `tests/test_mcp.py` and the allow-list test. Kitchen must not receive a booking tool, and the reverse.

## Status values

- `ok` — read finished
- `pending_approval` — proposal only
- `completed` — commit ran after approval
- `rejected` — guest said no; files unchanged
- `refused` — rule blocked it (closed, stock, bad status)
- `needs_detail` — ask, do not guess
- `error` — missing guest, missing booking, missing approval token
