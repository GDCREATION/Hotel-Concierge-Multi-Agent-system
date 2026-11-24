from __future__ import annotations

from uuid import uuid4

from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import (
    committed_result,
    get_proposal,
    is_approved,
    mark_committed,
    save_proposal,
)
from hostel_concierge.store import GUESTS_FILE, read_json, write_json

_ACTIONS = {
    "check-in": "checked-in",
    "check-out": "checked-out",
}
_REQUIRED_STATUS = {
    "check-in": "booked",
    "check-out": "checked-in",
}


def resolve_guest(guest: GuestContext) -> dict | None:
    for record in read_json(GUESTS_FILE):
        if record["id"] == guest.guest_id and record["room"] == guest.room:
            return record
    return None


def get_my_booking(guest: GuestContext) -> dict:
    record = resolve_guest(guest)
    if record is None:
        return {
            "status": "error",
            "code": "booking_not_found",
            "message": "I couldn't find a booking for the logged-in guest.",
        }
    return {
        "status": "ok",
        "booking": record,
        "message": (
            f"You are in room {record['room']}. "
            f"Check-in {record['check_in']}, checkout {record['check_out']}, "
            f"status {record['status']}."
        ),
    }


def propose_status_change(guest: GuestContext, action: str, when: str) -> dict:
    normalized = (action or "").strip().lower()
    if normalized not in _ACTIONS:
        return {
            "status": "needs_detail",
            "message": "Do you want to check in or check out?",
        }
    when_text = (when or "").strip()
    if not when_text:
        return {
            "status": "needs_detail",
            "message": f"What time should I use for {normalized}?",
        }
    record = resolve_guest(guest)
    if record is None:
        return {
            "status": "error",
            "code": "booking_not_found",
            "message": "I couldn't find a booking for the logged-in guest.",
        }
    expected = _REQUIRED_STATUS[normalized]
    if record["status"] != expected:
        return {
            "status": "refused",
            "code": "invalid_transition",
            "message": (
                f"Can't {normalized} room {record['room']} because the booking status is "
                f"{record['status']}, not {expected}."
            ),
        }
    proposal = {
        "id": f"book_{uuid4().hex[:10]}",
        "type": "booking",
        "action": normalized,
        "when": when_text,
        "guest_id": record["id"],
        "name": record["name"],
        "room": record["room"],
        "from_status": record["status"],
        "to_status": _ACTIONS[normalized],
        "booked_checkout": record["check_out"],
    }
    save_proposal(proposal)
    return {
        "status": "pending_approval",
        "tool": "request_check_in_or_out",
        "proposal": proposal,
        "message": (
            f"Proposed {normalized} for {record['name']} in room {record['room']} ({when_text}). "
            f"Status would change from {record['status']} to {proposal['to_status']}. "
            f"Booked checkout date is {record['check_out']}. "
            "Nothing has been changed yet."
        ),
    }


def commit(proposal_id: str) -> dict:
    """Apply a booking change. Refuses unless grant_approval already ran."""

    existing = committed_result(proposal_id)
    if existing is not None:
        return existing
    if not is_approved(proposal_id):
        return {
            "status": "error",
            "code": "approval_missing",
            "commit_tool": "commit_booking",
            "message": "This booking change was not approved, so nothing was updated.",
        }
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return {
            "status": "error",
            "code": "proposal_missing",
            "commit_tool": "commit_booking",
            "message": "That booking proposal is no longer available, so nothing was updated.",
        }
    guests = read_json(GUESTS_FILE)
    for record in guests:
        if record["id"] == proposal["guest_id"] and record["room"] == proposal["room"]:
            if record["status"] != proposal["from_status"]:
                return {
                    "status": "refused",
                    "code": "invalid_transition",
                    "commit_tool": "commit_booking",
                    "message": (
                        f"Can't {proposal['action']} room {record['room']} because the booking status is "
                        f"{record['status']}, not {proposal['from_status']}."
                    ),
                }
            record["status"] = proposal["to_status"]
            record["last_request"] = {
                "action": proposal["action"],
                "when": proposal["when"],
            }
            write_json(GUESTS_FILE, guests)
            verb = "Check-in" if proposal["action"] == "check-in" else "Checkout"
            result = {
                "status": "completed",
                "commit_tool": "commit_booking",
                "proposal": proposal,
                "message": (
                    f"{verb} confirmed for room {proposal['room']} ({proposal['when']}). "
                    f"Status is now {proposal['to_status']}."
                ),
            }
            mark_committed(proposal_id, result)
            return result
    return {
        "status": "error",
        "code": "booking_not_found",
        "commit_tool": "commit_booking",
        "message": "I couldn't find a booking for the logged-in guest.",
    }
