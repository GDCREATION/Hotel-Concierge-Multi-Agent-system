"""Human approval enforced before any booking or order write.

MCP tools only propose. Commit functions live outside the model tool list and
refuse to run unless grant_approval() recorded the proposal id.
"""

from __future__ import annotations

from langgraph.types import interrupt

from hostel_concierge import booking_service, kitchen_service
from hostel_concierge.mcp_client import mcp_call
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import bind_guest, grant_approval
from hostel_concierge.safety.allowlist import allowed_tool_names
from hostel_concierge.safety.config import approval_required_tools

_IDENTITY_KEYS = {"guest_id", "room", "guest", "guest_room"}
_COMMITTERS = {
    "request_check_in_or_out": booking_service.commit,
    "place_room_order": kitchen_service.commit,
}


def strip_identity(args: dict | None) -> dict:
    payload = args or {}
    return {key: value for key, value in payload.items() if key not in _IDENTITY_KEYS}


def run_gated_or_direct(
    agent: str,
    tool_name: str,
    args: dict | None,
    guest: GuestContext,
) -> dict:
    if tool_name not in allowed_tool_names(agent):
        return {
            "status": "error",
            "code": "tool_not_allowed",
            "message": f"{tool_name} is not allowed for the {agent} specialist.",
        }
    bind_guest(guest)
    safe_args = strip_identity(args)
    if tool_name not in approval_required_tools():
        result = mcp_call(tool_name, safe_args)
        result["steps"] = [tool_name]
        return result

    preview = mcp_call(tool_name, safe_args)
    if preview.get("status") != "pending_approval":
        preview["steps"] = [tool_name]
        return preview

    decision = interrupt(
        {
            "agent": agent,
            "tool": tool_name,
            "proposal": preview["proposal"],
            "message": preview["message"],
        }
    )
    approved = isinstance(decision, dict) and bool(decision.get("approved"))
    if not approved:
        return {
            "status": "rejected",
            "message": "The guest rejected this action. Nothing was changed.",
            "proposal": preview.get("proposal"),
            "steps": [tool_name, "rejected"],
        }
    grant_approval(preview["proposal"]["id"])
    committed = _COMMITTERS[tool_name](preview["proposal"]["id"])
    commit_name = committed.get("commit_tool", "commit")
    committed["steps"] = [tool_name, commit_name]
    return committed
