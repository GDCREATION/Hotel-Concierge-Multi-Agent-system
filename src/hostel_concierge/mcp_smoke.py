"""Call the four MCP tools in-process and show that gated tools do not write data."""

import json
import os

from hostel_concierge.mcp_client import mcp_call, mcp_tool_names
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import bind_guest, reset_runtime
from hostel_concierge.store import GUESTS_FILE, MENU_FILE, read_json


def main() -> None:
    os.environ.setdefault("HOSTEL_NOW", "2026-11-24T08:30:00")
    reset_runtime()
    bind_guest(GuestContext(guest_id="g-305", room="305"))
    print("tools:", sorted(mcp_tool_names()))
    before_guests = read_json(GUESTS_FILE)
    before_menu = read_json(MENU_FILE)
    calls = [
        ("get_my_booking", {}),
        ("request_check_in_or_out", {"action": "check-out", "when": "tomorrow at 7 am"}),
        ("get_menu_and_kitchen_status", {}),
        ("place_room_order", {"items": ["Veg Sandwich", "Coffee"]}),
    ]
    for name, args in calls:
        print(f"\n== {name} ==")
        print(json.dumps(mcp_call(name, args), indent=2))
    assert read_json(GUESTS_FILE) == before_guests
    assert read_json(MENU_FILE) == before_menu
    print("\nGated tools left the mock files unchanged.")


if __name__ == "__main__":
    main()
