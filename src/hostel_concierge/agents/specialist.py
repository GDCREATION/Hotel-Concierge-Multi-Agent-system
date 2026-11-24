"""Specialists do not see the guest chat. They receive one complete instruction and their own tools."""

from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from hostel_concierge.agents.llm import build_chat_model, invoke_model
from hostel_concierge.agents.prompts import BOOKING_PROMPT, KITCHEN_PROMPT
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import bind_guest
from hostel_concierge.safety.allowlist import visible_tools
from hostel_concierge.safety.approval import run_gated_or_direct
from hostel_concierge.safety.limits import CallLimiter, limiter_for
from hostel_concierge.mcp_client import mcp_tool_names
from hostel_concierge.scope import other_rooms, scope_block_message

_PROMPTS = {"booking": BOOKING_PROMPT, "kitchen": KITCHEN_PROMPT}


@tool
def get_my_booking() -> str:
    """Return the logged-in guest's room, check-in date, checkout date, and status. Call this for any booking lookup."""

    return "schema"


@tool
def request_check_in_or_out(action: str, when: str) -> str:
    """Propose check-in or check-out. action is check-in or check-out. when is the time the guest gave. Does not change the booking."""

    return "schema"


@tool
def get_menu_and_kitchen_status() -> str:
    """Return the menu, prices, stock, allergens, and whether the kitchen is open now."""

    return "schema"


@tool
def place_room_order(items: list[str]) -> str:
    """Propose an order for these exact menu item names. Does not send the order or change stock."""

    return "schema"


_TOOLBOX = {
    "get_my_booking": get_my_booking,
    "request_check_in_or_out": request_check_in_or_out,
    "get_menu_and_kitchen_status": get_menu_and_kitchen_status,
    "place_room_order": place_room_order,
}


def tools_for(agent: str) -> list:
    names = visible_tools(agent, mcp_tool_names())
    return [_TOOLBOX[name] for name in names]


def _payload(agent: str, status: str, message: str, tool_trace: list[dict]) -> str:
    return json.dumps(
        {
            "specialist": agent,
            "status": status,
            "message": message,
            "tool_trace": tool_trace,
        }
    )


def _status_from_messages(messages: list) -> str:
    status = "ok"
    for message in messages:
        if isinstance(message, ToolMessage):
            try:
                status = json.loads(message.content).get("status", status)
            except json.JSONDecodeError:
                status = "error"
    return status


def run_specialist(
    agent: str,
    instruction: str,
    guest: GuestContext,
    *,
    model=None,
    limiter: CallLimiter | None = None,
) -> str:
    blocked = other_rooms(instruction, guest.room)
    if blocked:
        return _payload(agent, "blocked", scope_block_message(guest.room, blocked[0], agent), [])

    bind_guest(guest)
    limiter = limiter or limiter_for(agent)
    model = model or build_chat_model(agent)
    tools = tools_for(agent)
    allowed = {tool.name for tool in tools}
    messages: list = [SystemMessage(content=_PROMPTS[agent]), HumanMessage(content=instruction)]
    tool_trace: list[dict] = []

    while True:
        if not limiter.allow_model():
            return _payload(agent, "limit", limiter.model_stop_message(), tool_trace)
        ai = invoke_model(model, messages, tools)
        if not ai.tool_calls:
            return _payload(agent, _status_from_messages(messages), ai.content or "", tool_trace)
        messages.append(ai)
        for call in ai.tool_calls:
            name = call["name"]
            args = call.get("args") or {}
            if name not in allowed:
                result = {
                    "status": "error",
                    "code": "tool_not_allowed",
                    "message": f"{name} is not allowed for the {agent} specialist.",
                }
            elif not limiter.allow_tool(name):
                return _payload(agent, "limit", limiter.tool_stop_message(name), tool_trace)
            else:
                result = run_gated_or_direct(agent, name, args, guest)
            tool_trace.append({"tool": name, "status": result.get("status"), "steps": result.get("steps", [])})
            messages.append(ToolMessage(content=json.dumps(result), tool_call_id=call["id"]))
