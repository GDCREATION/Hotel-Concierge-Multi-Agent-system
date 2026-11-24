from hostel_concierge.agents.orchestrator import ORCHESTRATOR_TOOL_NAMES
from hostel_concierge.agents.specialist import tools_for
from hostel_concierge.models import GuestContext
from hostel_concierge.safety.allowlist import visible_tools
from hostel_concierge.safety.approval import run_gated_or_direct
from hostel_concierge.safety.limits import CallLimiter
from hostel_concierge.scope import other_rooms


def test_other_room_is_detected_and_own_room_is_not():
    assert other_rooms("Show me the booking for room 204.", "305") == ["204"]
    assert other_rooms("Which room am I in?", "305") == []
    assert other_rooms("I am in room 305.", "305") == []


def test_allowlists_are_disjoint_even_if_discovery_returns_every_tool():
    discovered = {
        "get_my_booking",
        "request_check_in_or_out",
        "get_menu_and_kitchen_status",
        "place_room_order",
        "commit_booking",
        "commit_room_order",
    }
    booking = set(visible_tools("booking", discovered))
    kitchen = set(visible_tools("kitchen", discovered))
    assert booking == {"get_my_booking", "request_check_in_or_out"}
    assert kitchen == {"get_menu_and_kitchen_status", "place_room_order"}
    assert booking.isdisjoint(kitchen)


def test_live_mcp_tools_follow_the_same_split():
    booking = {tool.name for tool in tools_for("booking")}
    kitchen = {tool.name for tool in tools_for("kitchen")}
    assert "place_room_order" not in booking
    assert "get_my_booking" not in kitchen
    assert "request_check_in_or_out" not in kitchen
    assert "get_menu_and_kitchen_status" not in booking


def test_orchestrator_has_no_business_tools():
    assert ORCHESTRATOR_TOOL_NAMES == ("call_booking_specialist", "call_kitchen_specialist")


def test_model_supplied_room_does_not_override_context():
    guest = GuestContext(guest_id="g-305", room="305")
    result = run_gated_or_direct(
        "booking",
        "get_my_booking",
        {"room": "204", "guest_id": "g-204"},
        guest,
    )
    assert result["booking"]["room"] == "305"
    assert result["booking"]["name"] == "Asha Menon"
    assert "Liam" not in result["message"]


def test_kitchen_cannot_call_a_booking_tool():
    result = run_gated_or_direct(
        "kitchen",
        "get_my_booking",
        {},
        GuestContext(guest_id="g-305", room="305"),
    )
    assert result["code"] == "tool_not_allowed"


def test_booking_cannot_call_a_kitchen_tool():
    result = run_gated_or_direct(
        "booking",
        "place_room_order",
        {"items": ["Coffee"]},
        GuestContext(guest_id="g-305", room="305"),
    )
    assert result["code"] == "tool_not_allowed"


def test_call_limiter_stops_with_a_clear_message():
    limiter = CallLimiter("kitchen", max_model_calls=1, max_tool_calls=1)
    assert limiter.allow_model() is True
    assert limiter.allow_model() is False
    assert "Stopped: kitchen reached the model-call limit" in limiter.model_stop_message()
    assert limiter.allow_tool("place_room_order") is True
    assert limiter.allow_tool("place_room_order") is False
    assert "place_room_order" in limiter.tool_stop_message("place_room_order")
