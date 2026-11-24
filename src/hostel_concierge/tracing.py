from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from hostel_concierge.session import TurnResult, message_text


def _role(message) -> str:
    if isinstance(message, HumanMessage):
        return "guest"
    if isinstance(message, AIMessage):
        return "orchestrator"
    if isinstance(message, ToolMessage):
        return f"tool:{message.name or 'result'}"
    return message.type


def render_turns(title: str, prompts: list[str], turns: list[TurnResult], *, clock: str, room: str) -> str:
    lines = [
        f"# {title}",
        "",
        f"Logged-in guest: room {room}. The guest did not type an id.",
        f"Clock: {clock}",
        "",
    ]
    for index, (prompt, turn) in enumerate(zip(prompts, turns), start=1):
        lines.append(f"## Turn {index}")
        lines.append("")
        lines.append(f"**Guest:** {prompt}")
        lines.append("")
        if turn.approvals:
            lines.append("### Approval pauses")
            lines.append("")
            for approval in turn.approvals:
                lines.append(f"- Tool `{approval.get('tool')}` on agent `{approval.get('agent')}`")
                lines.append(f"  - {approval.get('message')}")
            lines.append("")
        lines.append("### Delegations and specialist tools")
        lines.append("")
        for message in turn.messages:
            if isinstance(message, AIMessage) and message.tool_calls:
                for call in message.tool_calls:
                    args = call.get("args") or {}
                    if "instruction" in args:
                        lines.append(f"- `{call['name']}`")
                        lines.append("")
                        lines.append("```text")
                        lines.append(str(args["instruction"]))
                        lines.append("```")
                        lines.append("")
            if isinstance(message, ToolMessage):
                lines.append(f"- Result from `{message.name}`")
                lines.append("")
                try:
                    data = json.loads(message.content)
                except json.JSONDecodeError:
                    lines.append(message.content)
                    lines.append("")
                    continue
                lines.append(f"  - status: `{data.get('status')}`")
                if data.get("tool_trace"):
                    rendered = ", ".join(
                        f"{step.get('tool')} ({step.get('status')})" for step in data["tool_trace"]
                    )
                    lines.append(f"  - tools: {rendered}")
                lines.append("")
        lines.append("### Reply")
        lines.append("")
        lines.append(turn.reply)
        lines.append("")
    lines.append("## Session messages after the last turn")
    lines.append("")
    if turns:
        for message in turns[-1].messages:
            text = message_text(getattr(message, "content", ""))
            if isinstance(message, AIMessage) and message.tool_calls and not text:
                text = ", ".join(call["name"] for call in message.tool_calls)
            lines.append(f"- {_role(message)}: {text}")
    lines.append("")
    return "\n".join(lines)
