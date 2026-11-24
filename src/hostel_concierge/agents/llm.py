"""Model boundary. Live calls use Amazon Bedrock. HOSTEL_MODEL=scripted skips AWS."""

from __future__ import annotations

import json
import os
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from hostel_concierge.agents.policy import (
    booking_mode,
    classify,
    extract_when,
    kitchen_mode,
    match_item_names,
)


def _human_texts(messages: list[BaseMessage]) -> list[str]:
    return [message.content for message in messages if isinstance(message, HumanMessage)]


def _render_tools(messages: list[BaseMessage]) -> str:
    trail: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, ToolMessage):
            break
        trail.append(message.content)
    parts: list[str] = []
    for raw in reversed(trail):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            parts.append(str(raw))
            continue
        if isinstance(data, dict) and data.get("message"):
            parts.append(str(data["message"]))
        else:
            parts.append(str(raw))
    return "\n\n".join(parts)


def _tool_call(name: str, args: dict, call_id: str | None = None) -> dict:
    return {
        "name": name,
        "args": args,
        "id": call_id or f"call_{name}",
        "type": "tool_call",
    }


def decide_orchestrator(messages: list[BaseMessage]) -> AIMessage:
    texts = _human_texts(messages)
    latest = texts[-1] if texts else ""
    history = texts[:-1]
    decision = classify(latest, history)
    if messages and isinstance(messages[-1], ToolMessage):
        body = _render_tools(messages)
        if decision.follow_up:
            body = f"{body}\n\n{decision.follow_up}" if body else decision.follow_up
        return AIMessage(content=body)
    if decision.kind != "delegate":
        return AIMessage(content=decision.message)
    calls = [
        _tool_call(
            f"call_{specialist}_specialist",
            {"instruction": decision.instructions[specialist]},
            call_id=f"call_{specialist}",
        )
        for specialist in decision.specialists
    ]
    return AIMessage(content="", tool_calls=calls)


def decide_booking(messages: list[BaseMessage]) -> AIMessage:
    if messages and isinstance(messages[-1], ToolMessage):
        return AIMessage(content=_render_tools(messages))
    instruction = _human_texts(messages)[-1]
    mode = booking_mode(instruction)
    if mode in {"check-in", "check-out"}:
        return AIMessage(
            content="",
            tool_calls=[
                _tool_call(
                    "request_check_in_or_out",
                    {"action": mode, "when": extract_when(instruction) or ""},
                )
            ],
        )
    if mode == "unclear-action":
        return AIMessage(content="Do you want to check in or check out?")
    return AIMessage(content="", tool_calls=[_tool_call("get_my_booking", {})])


def decide_kitchen(messages: list[BaseMessage]) -> AIMessage:
    if messages and isinstance(messages[-1], ToolMessage):
        return AIMessage(content=_render_tools(messages))
    instruction = _human_texts(messages)[-1]
    mode = kitchen_mode(instruction)
    if mode == "ask-items":
        return AIMessage(content="What would you like to order? I need the item names.")
    if mode == "order":
        return AIMessage(
            content="",
            tool_calls=[_tool_call("place_room_order", {"items": match_item_names(instruction)})],
        )
    return AIMessage(content="", tool_calls=[_tool_call("get_menu_and_kitchen_status", {})])


_DECIDERS = {
    "orchestrator": decide_orchestrator,
    "booking": decide_booking,
    "kitchen": decide_kitchen,
}


class ScriptedChatModel(BaseChatModel):
    """Tool-calling stand-in so the graph can be graded without an API key."""

    role: str = "orchestrator"

    @property
    def _llm_type(self) -> str:
        return f"scripted-{self.role}"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        message = _DECIDERS[self.role](list(messages))
        return ChatResult(generations=[ChatGeneration(message=message)])


class LoopingChatModel(BaseChatModel):
    """Always requests the same tool, so call limits have a loop to stop."""

    tool_name: str = "get_my_booking"
    tool_args: dict = Field(default_factory=dict)

    @property
    def _llm_type(self) -> str:
        return "looping"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ANN001
        message = AIMessage(
            content="",
            tool_calls=[_tool_call(self.tool_name, dict(self.tool_args), call_id=f"loop_{uuid4().hex[:8]}")],
        )
        return ChatResult(generations=[ChatGeneration(message=message)])


# Inference profile, not the EOL on-demand Claude 3 id. Tool calling verified on this account.
DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
_BEDROCK_MODEL: BaseChatModel | None = None


def message_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("text"):
                parts.append(str(block["text"]))
        return "".join(parts)
    return str(content or "")


def build_bedrock_model() -> BaseChatModel:
    """ChatBedrockConverse uses the default AWS credential chain (env, profile, SSO)."""

    global _BEDROCK_MODEL
    if _BEDROCK_MODEL is not None:
        return _BEDROCK_MODEL
    from langchain_aws import ChatBedrockConverse

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    _BEDROCK_MODEL = ChatBedrockConverse(
        model=os.environ.get("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID),
        region_name=region,
        temperature=0,
    )
    return _BEDROCK_MODEL


def build_chat_model(role: str) -> BaseChatModel:
    kind = os.environ.get("HOSTEL_MODEL", "bedrock").strip().lower()
    if kind == "scripted":
        return ScriptedChatModel(role=role)
    if kind in {"bedrock", "aws"}:
        return build_bedrock_model()
    raise ValueError(f"Unknown HOSTEL_MODEL={kind!r}. Use 'bedrock' or 'scripted'.")


def invoke_model(model: BaseChatModel, messages: list[BaseMessage], tools: list) -> AIMessage:
    bound = model.bind_tools(tools) if tools else model
    result = bound.invoke(messages)
    if not isinstance(result, AIMessage):
        return AIMessage(content=str(result))
    if isinstance(result.content, list):
        text = message_text(result.content)
        if result.tool_calls:
            return AIMessage(content=text, tool_calls=result.tool_calls, id=result.id)
        return AIMessage(content=text, id=result.id)
    return result
