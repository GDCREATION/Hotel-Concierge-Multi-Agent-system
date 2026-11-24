"""The only guest-facing agent. Specialists are tools. Business tools are not on this graph."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from hostel_concierge.agents.llm import build_chat_model, invoke_model
from hostel_concierge.agents.prompts import ORCHESTRATOR_PROMPT
from hostel_concierge.agents.specialist import run_specialist
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import bind_guest
from hostel_concierge.safety.config import limits_for
from hostel_concierge.safety.limits import model_limit_message, tool_limit_message

ORCHESTRATOR_TOOL_NAMES = ("call_booking_specialist", "call_kitchen_specialist")


class GraphState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    guest_id: str
    room: str
    orch_model_calls: int
    orch_tool_counts: dict
    halt: bool


@tool
def call_booking_specialist(instruction: str) -> str:
    """Answer the logged-in guest's room, dates, status, check-in, or checkout. Pass their full request as instruction."""

    return "executed-by-graph"


@tool
def call_kitchen_specialist(instruction: str) -> str:
    """Answer menu, kitchen hours, stock, or a room food order. Pass their full request as instruction."""

    return "executed-by-graph"


_SCHEMAS = {
    "call_booking_specialist": call_booking_specialist,
    "call_kitchen_specialist": call_kitchen_specialist,
}


def _guest_from_state(state: GraphState) -> GuestContext:
    return GuestContext(guest_id=state["guest_id"], room=state["room"])


def build_app(orchestrator_model=None, limit_overrides: dict | None = None):
    """Compile the orchestrator. Pass a model to force the looping demo without touching config."""

    def call_model(state: GraphState):
        limits = limits_for("orchestrator", limit_overrides)
        used = int(state.get("orch_model_calls") or 0) + 1
        if used > int(limits["max_model_calls"]):
            return {
                "orch_model_calls": used,
                "halt": True,
                "messages": [
                    AIMessage(content=model_limit_message("orchestrator", int(limits["max_model_calls"])))
                ],
            }
        model = orchestrator_model or build_chat_model("orchestrator")
        tools = [_SCHEMAS[name] for name in ORCHESTRATOR_TOOL_NAMES]
        ai = invoke_model(model, [SystemMessage(content=ORCHESTRATOR_PROMPT), *state.get("messages", [])], tools)
        return {"messages": [ai], "orch_model_calls": used, "halt": False}

    def run_tools(state: GraphState):
        limits = limits_for("orchestrator", limit_overrides)
        maximum = int(limits["max_tool_calls"])
        guest = _guest_from_state(state)
        bind_guest(guest)
        counts = dict(state.get("orch_tool_counts") or {})
        last = state["messages"][-1]
        outputs = []
        for call in last.tool_calls:
            name = call["name"]
            counts[name] = counts.get(name, 0) + 1
            if name not in _SCHEMAS:
                content = (
                    '{"status":"error","message":"'
                    + f"{name} is not an orchestrator tool. Booking and kitchen tools stay with the specialists."
                    + '"}'
                )
            elif counts[name] > maximum:
                content = tool_limit_message("orchestrator", name, maximum)
            else:
                instruction = str((call.get("args") or {}).get("instruction") or "")
                agent = "booking" if name == "call_booking_specialist" else "kitchen"
                content = run_specialist(agent, instruction, guest)
            outputs.append({"role": "tool", "name": name, "content": content, "tool_call_id": call["id"]})
        from langchain_core.messages import ToolMessage

        return {
            "messages": [
                ToolMessage(content=item["content"], tool_call_id=item["tool_call_id"], name=item["name"])
                for item in outputs
            ],
            "orch_tool_counts": counts,
        }

    def route_after_model(state: GraphState):
        if state.get("halt"):
            return END
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return END

    graph = StateGraph(GraphState)
    graph.add_node("orchestrator", call_model)
    graph.add_node("tools", run_tools)
    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", route_after_model, {"tools": "tools", END: END})
    graph.add_edge("tools", "orchestrator")
    return graph.compile(checkpointer=InMemorySaver())


_APP = None


def get_app():
    global _APP
    if _APP is None:
        _APP = build_app()
    return _APP
