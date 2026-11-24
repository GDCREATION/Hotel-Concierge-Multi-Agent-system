from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from hostel_concierge.agents.orchestrator import get_app
from hostel_concierge.models import GuestContext
from hostel_concierge.store import GUESTS_FILE, read_json


@dataclass
class TurnResult:
    reply: str
    approvals: list[dict] = field(default_factory=list)
    messages: list = field(default_factory=list)
    pending: bool = False


def guest_in_room(room: str = "305") -> GuestContext:
    for record in read_json(GUESTS_FILE):
        if record["room"] == str(room):
            return GuestContext(guest_id=record["id"], room=record["room"])
    raise KeyError(f"No guest is booked in room {room}")


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                parts.append(str(block.get("text", "")))
        return "".join(parts)
    return str(content)


def final_reply(result: dict) -> str:
    for message in reversed(result.get("messages", [])):
        if isinstance(message, AIMessage) and not message.tool_calls:
            return message_text(message.content)
    return ""


def interrupt_values(result: dict) -> list[dict]:
    values = []
    for item in result.get("__interrupt__") or []:
        value = getattr(item, "value", item)
        if isinstance(value, dict):
            values.append(value)
    return values


def inspect_turn(turn: TurnResult) -> dict:
    """Summarize specialists, tools, and any pending approval for the demo UI."""
    specialists: list[str] = []
    tools: list[str] = []
    for message in turn.messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            for call in message.tool_calls:
                name = call.get("name") or ""
                if name in {"call_booking_specialist", "call_kitchen_specialist"}:
                    specialists.append(name)
                elif name:
                    tools.append(name)
        if isinstance(message, ToolMessage):
            try:
                data = json.loads(message.content)
            except (TypeError, json.JSONDecodeError):
                continue
            for step in data.get("tool_trace") or []:
                tool = step.get("tool")
                status = step.get("status")
                if tool:
                    tools.append(f"{tool} ({status})" if status else str(tool))
            for step in data.get("steps") or []:
                if isinstance(step, str) and step not in tools:
                    tools.append(step)
    pending = turn.approvals[-1] if turn.pending and turn.approvals else None
    return {
        "specialists": specialists,
        "tools": tools,
        "pending": pending,
        "status": "awaiting_approval" if turn.pending else "completed",
    }


class Session:
    def __init__(self, guest: GuestContext, app=None):
        self.guest = guest
        self.app = app or get_app()
        self.config = {"configurable": {"thread_id": uuid4().hex}}

    @classmethod
    def start(cls, guest: GuestContext | None = None, app=None) -> Session:
        return cls(guest or guest_in_room("305"), app=app)

    def ask_until_interrupt(self, text: str) -> TurnResult:
        result = self.app.invoke(
            {
                "messages": [HumanMessage(content=text)],
                "guest_id": self.guest.guest_id,
                "room": self.guest.room,
                "orch_model_calls": 0,
                "orch_tool_counts": {},
                "halt": False,
            },
            self.config,
        )
        return self._turn_from_result(result, [])

    def resume(self, approved: bool, prior_approvals: list[dict] | None = None) -> TurnResult:
        result = self.app.invoke(Command(resume={"approved": bool(approved)}), self.config)
        return self._turn_from_result(result, list(prior_approvals or []))

    def ask(
        self,
        text: str,
        decision_source: list[bool] | None = None,
        *,
        interactive: bool = False,
    ) -> TurnResult:
        turn = self.ask_until_interrupt(text)
        approvals = list(turn.approvals)
        while turn.pending:
            approved = _decide(turn.approvals[-1], decision_source, interactive)
            turn = self.resume(approved, prior_approvals=approvals)
            approvals = list(turn.approvals)
        return turn

    def _turn_from_result(self, result: dict, approvals: list[dict]) -> TurnResult:
        pending = interrupt_values(result)
        messages = list(result.get("messages") or [])
        if pending:
            return TurnResult(
                reply="",
                approvals=approvals + [pending[0]],
                messages=messages,
                pending=True,
            )
        return TurnResult(
            reply=final_reply(result),
            approvals=approvals,
            messages=messages,
            pending=False,
        )


def _decide(payload: dict, decision_source: list[bool] | None, interactive: bool) -> bool:
    if interactive:
        return _prompt_approval(payload)
    if not decision_source:
        raise RuntimeError("This action needs approval, but no decision was provided.")
    return bool(decision_source.pop(0))


def _prompt_approval(payload: dict) -> bool:
    from rich.console import Console
    from rich.panel import Panel

    console = Console()
    proposal = payload.get("proposal") or {}
    lines = [
        payload.get("message") or "Approve this action?",
        f"Agent: {payload.get('agent')}  Tool: {payload.get('tool')}",
        "Nothing is saved until you approve.",
    ]
    if proposal:
        lines.append(f"Proposal {proposal.get('id')} for room {proposal.get('room')}.")
    console.print(Panel("\n".join(lines), title="Approval needed"))
    answer = console.input("Approve? [y/n]: ").strip().lower()
    return answer in {"y", "yes", "approve"}
