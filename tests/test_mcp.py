from hostel_concierge.mcp_client import mcp_call, mcp_tool_names
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import bind_guest
from hostel_concierge.store import GUESTS_FILE, MENU_FILE, read_json


def test_server_exposes_the_four_public_tools():
    assert set(mcp_tool_names()) == {
        "get_my_booking",
        "request_check_in_or_out",
        "get_menu_and_kitchen_status",
        "place_room_order",
    }


def test_gated_mcp_tools_do_not_mutate():
    bind_guest(GuestContext(guest_id="g-305", room="305"))
    before_guests = read_json(GUESTS_FILE)
    before_menu = read_json(MENU_FILE)
    booking = mcp_call("get_my_booking", {})
    proposal = mcp_call(
        "request_check_in_or_out",
        {"action": "check-out", "when": "tomorrow at 7 am"},
    )
    menu = mcp_call("get_menu_and_kitchen_status", {})
    order = mcp_call("place_room_order", {"items": ["Veg Sandwich", "Coffee"]})
    assert booking["status"] == "ok"
    assert proposal["status"] == "pending_approval"
    assert menu["status"] == "ok"
    assert order["status"] == "pending_approval"
    assert read_json(GUESTS_FILE) == before_guests
    assert read_json(MENU_FILE) == before_menu


def test_booking_not_found_is_a_payload():
    bind_guest(GuestContext(guest_id="missing", room="999"))
    result = mcp_call("get_my_booking", {})
    assert result["code"] == "booking_not_found"
