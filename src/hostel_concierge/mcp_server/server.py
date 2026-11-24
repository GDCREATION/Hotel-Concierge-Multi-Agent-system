"""MCP tools for Sunrise Hostel. Identity is read from the app binding, never from arguments."""

from fastmcp import FastMCP

from hostel_concierge import booking_service, kitchen_service
from hostel_concierge.runtime_state import MissingGuest, require_guest

mcp = FastMCP(
    "sunrise-hostel",
    instructions=(
        "Hostel tools for the guest already bound by the application. "
        "Do not pass guest id or room; those values are ignored."
    ),
)


def _guest_error() -> dict:
    return {
        "status": "error",
        "code": "guest_missing",
        "message": "No logged-in guest is bound, so I can't use room or booking data.",
    }


def _guard(fn):
    try:
        return fn()
    except MissingGuest:
        return _guest_error()
    except Exception as exc:  # noqa: BLE001 - tool boundary must not crash the guest chat
        return {
            "status": "error",
            "code": "tool_error",
            "message": "That request failed before I could finish it.",
            "detail": str(exc),
        }


@mcp.tool(run_in_thread=False)
def get_my_booking() -> dict:
    """Read the logged-in guest's room, dates, and status. No approval."""

    return _guard(lambda: booking_service.get_my_booking(require_guest()))


@mcp.tool(run_in_thread=False)
def request_check_in_or_out(action: str, when: str) -> dict:
    """Propose check-in or check-out. Does not change the booking."""

    def propose() -> dict:
        guest = require_guest()
        return booking_service.propose_status_change(guest, action, when)

    return _guard(propose)


@mcp.tool(run_in_thread=False)
def get_menu_and_kitchen_status() -> dict:
    """Read the menu, stock, allergens, and whether the kitchen is open now. No approval."""

    return _guard(kitchen_service.get_menu_and_kitchen_status)


@mcp.tool(run_in_thread=False)
def place_room_order(items: list[str]) -> dict:
    """Propose an order for the logged-in guest's room. Does not decrement stock."""

    def propose() -> dict:
        guest = require_guest()
        return kitchen_service.propose_order(guest, items)

    return _guard(propose)


def main() -> None:
    mcp.run(transport="stdio", show_banner=False)
