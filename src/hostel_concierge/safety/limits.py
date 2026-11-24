from dataclasses import dataclass, field

from hostel_concierge.safety.config import limits_for


def model_limit_message(agent: str, maximum: int) -> str:
    return f"Stopped: {agent} reached the model-call limit ({maximum} per request)."


def tool_limit_message(agent: str, tool_name: str, maximum: int) -> str:
    return (
        f"Stopped: {agent} reached the tool-call limit for {tool_name} "
        f"({maximum} per request)."
    )


@dataclass
class CallLimiter:
    """Counts model and tool calls for one agent inside one specialist run."""

    agent: str
    max_model_calls: int
    max_tool_calls: int
    model_calls: int = 0
    tool_calls: dict[str, int] = field(default_factory=dict)

    def allow_model(self) -> bool:
        self.model_calls += 1
        return self.model_calls <= self.max_model_calls

    def allow_tool(self, name: str) -> bool:
        self.tool_calls[name] = self.tool_calls.get(name, 0) + 1
        return self.tool_calls[name] <= self.max_tool_calls

    def model_stop_message(self) -> str:
        return model_limit_message(self.agent, self.max_model_calls)

    def tool_stop_message(self, name: str) -> str:
        return tool_limit_message(self.agent, name, self.max_tool_calls)


def limiter_for(agent: str, overrides: dict | None = None) -> CallLimiter:
    configured = limits_for(agent, overrides)
    return CallLimiter(
        agent=agent,
        max_model_calls=int(configured["max_model_calls"]),
        max_tool_calls=int(configured["max_tool_calls"]),
    )
