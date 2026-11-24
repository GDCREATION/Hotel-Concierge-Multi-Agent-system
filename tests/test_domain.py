from hostel_concierge.booking_service import commit as commit_booking
from hostel_concierge.booking_service import get_my_booking, propose_status_change
from hostel_concierge.kitchen_service import commit as commit_order
from hostel_concierge.kitchen_service import get_menu_and_kitchen_status, kitchen_open, propose_order
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import grant_approval
from hostel_concierge.session import guest_in_room
from hostel_concierge.store import GUESTS_FILE, MENU_FILE, ORDERS_FILE, read_json


def test_demo_guest_and_edge_statuses():
    guest = guest_in_room("305")
    assert guest.guest_id == "g-305"
    booking = get_my_booking(guest)
    assert booking["booking"]["status"] == "checked-in"
    assert booking["booking"]["check_out"] == "2026-11-26"
    statuses = {row["room"]: row["status"] for row in read_json(GUESTS_FILE)}
    assert statuses["101"] == "checked-out"
    assert statuses["412"] == "booked"


def test_menu_has_zero_stock_and_peanuts():
    menu = {item["name"]: item for item in read_json(MENU_FILE)}
    assert menu["Masala Omelette"]["stock"] == 0
    assert "peanuts" in menu["Peanut Chikki"]["allergens"]
    assert len(menu) >= 6


def test_kitchen_open_and_closed(monkeypatch):
    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T08:30:00")
    assert kitchen_open()["open"] is True
    assert kitchen_open()["meal"] == "breakfast"
    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T11:00:00")
    closed = kitchen_open()
    assert closed["open"] is False
    assert closed["next_meal"] == "lunch"


def test_checkout_proposal_does_not_write_until_approved():
    guest = guest_in_room("305")
    before = read_json(GUESTS_FILE)
    proposal = propose_status_change(guest, "check-out", "tomorrow at 7 am")
    assert proposal["status"] == "pending_approval"
    assert read_json(GUESTS_FILE) == before
    denied = commit_booking(proposal["proposal"]["id"])
    assert denied["code"] == "approval_missing"
    assert read_json(GUESTS_FILE) == before
    grant_approval(proposal["proposal"]["id"])
    done = commit_booking(proposal["proposal"]["id"])
    assert done["status"] == "completed"
    updated = next(row for row in read_json(GUESTS_FILE) if row["room"] == "305")
    assert updated["status"] == "checked-out"


def test_invalid_transitions():
    checked_out = GuestContext(guest_id="g-101", room="101")
    not_arrived = GuestContext(guest_id="g-412", room="412")
    staying = guest_in_room("305")
    assert propose_status_change(checked_out, "check-out", "tomorrow at 7 am")["code"] == "invalid_transition"
    assert propose_status_change(not_arrived, "check-out", "tomorrow at 7 am")["code"] == "invalid_transition"
    assert propose_status_change(staying, "check-in", "tomorrow at 8 am")["code"] == "invalid_transition"
    missing = propose_status_change(staying, "check-out", "")
    assert missing["status"] == "needs_detail"


def test_order_refuses_closed_kitchen_and_stock_and_commits_when_open(monkeypatch):
    guest = guest_in_room("305")
    before = read_json(MENU_FILE)
    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T11:00:00")
    closed = propose_order(guest, ["Veg Sandwich"])
    assert closed["code"] == "kitchen_closed"
    assert read_json(MENU_FILE) == before

    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T08:30:00")
    sold_out = propose_order(guest, ["Masala Omelette"])
    assert sold_out["code"] == "out_of_stock"
    assert read_json(MENU_FILE) == before

    pending = propose_order(guest, ["Veg Sandwich", "Coffee"])
    assert pending["status"] == "pending_approval"
    assert "peanuts" not in pending["message"]
    assert read_json(ORDERS_FILE) == []
    blocked = commit_order(pending["proposal"]["id"])
    assert blocked["code"] == "approval_missing"
    grant_approval(pending["proposal"]["id"])
    placed = commit_order(pending["proposal"]["id"])
    assert placed["status"] == "completed"
    menu = {item["name"]: item["stock"] for item in read_json(MENU_FILE)}
    assert menu["Veg Sandwich"] == 11
    assert menu["Coffee"] == 29
    assert read_json(ORDERS_FILE)[0]["room"] == "305"


def test_menu_status_mentions_allergens():
    message = get_menu_and_kitchen_status()["message"]
    assert "Peanut Chikki" in message
    assert "peanuts" in message
    assert "Masala Omelette" in message
