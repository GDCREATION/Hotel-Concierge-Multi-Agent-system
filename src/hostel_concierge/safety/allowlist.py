from hostel_concierge.safety.config import safety_config

PUBLIC_TOOLS = (
    "get_my_booking",
    "request_check_in_or_out",
    "get_menu_and_kitchen_status",
    "place_room_order",
)


def allowed_tool_names(agent: str) -> set[str]:
    return set(safety_config()["allowlists"][agent])


def visible_tools(agent: str, discovered: set[str]) -> list[str]:
    """Tools this specialist may see: MCP discovery intersected with its allow-list."""

    allowed = allowed_tool_names(agent)
    return [name for name in PUBLIC_TOOLS if name in discovered and name in allowed]
