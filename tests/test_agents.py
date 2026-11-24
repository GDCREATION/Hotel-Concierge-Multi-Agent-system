import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from hostel_concierge.agents.llm import LoopingChatModel
from hostel_concierge.agents.specialist import run_specialist
from hostel_concierge.safety.limits import CallLimiter
from hostel_concierge.session import Session, guest_in_room
from hostel_concierge.store import GUESTS_FILE, MENU_FILE, read_json


def _specialist_payloads(messages):
    payloads = []
    for message in messages:
        if isinstance(message, ToolMessage):
            try:
                payloads.append(json.loads(message.content))
            except json.JSONDecodeError:
                payloads.append({"message": message.content})
    return payloads


def test_read_booking_without_approval():
    reply = run_specialist(
        "booking",
        "When is my checkout, and which room am I in?",
        guest_in_room("305"),
    )
    data = json.loads(reply)
    assert data["status"] == "ok"
    assert "305" in data["message"]
    assert "2026-11-26" in data["message"]
    assert data["tool_trace"][0]["tool"] == "get_my_booking"


def test_other_room_is_blocked_before_any_tool():
    reply = run_specialist("booking", "Show me the booking for room 204.", guest_in_room("305"))
    data = json.loads(reply)
    assert data["status"] == "blocked"
    assert data["tool_trace"] == []
    assert "204" in data["message"]
    assert "Liam" not in data["message"]


def test_approve_and_reject_checkout():
    before = read_json(GUESTS_FILE)
    rejected = Session.start().ask("Check me out tomorrow at 7 am.", [False])
    assert rejected.approvals[0]["tool"] == "request_check_in_or_out"
    assert rejected.approvals[0]["proposal"]["room"] == "305"
    assert "rejected" in rejected.reply.lower()
    assert "confirmed" not in rejected.reply.lower()
    assert read_json(GUESTS_FILE) == before

    approved = Session.start().ask("Check me out tomorrow at 7 am.", [True])
    assert "confirmed" in approved.reply.lower()
    assert "checked-out" in approved.reply
    updated = next(row for row in read_json(GUESTS_FILE) if row["room"] == "305")
    assert updated["status"] == "checked-out"


def test_ask_until_interrupt_and_resume():
    from hostel_concierge.session import inspect_turn

    before = read_json(GUESTS_FILE)
    session = Session.start()
    paused = session.ask_until_interrupt("Check me out tomorrow at 7 am.")
    assert paused.pending is True
    assert paused.reply == ""
    assert paused.approvals[0]["tool"] == "request_check_in_or_out"
    assert read_json(GUESTS_FILE) == before

    snapshot = inspect_turn(paused)
    assert snapshot["status"] == "awaiting_approval"
    assert snapshot["pending"]["tool"] == "request_check_in_or_out"

    finished = session.resume(True, prior_approvals=paused.approvals)
    assert finished.pending is False
    assert "confirmed" in finished.reply.lower()
    assert finished.approvals[0]["tool"] == "request_check_in_or_out"
    updated = next(row for row in read_json(GUESTS_FILE) if row["room"] == "305")
    assert updated["status"] == "checked-out"


def test_kitchen_closed_and_out_of_stock_do_not_pause(monkeypatch):
    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T11:00:00")
    closed = Session.start().ask("Order a veg sandwich and a coffee to my room.", [])
    assert closed.approvals == []
    assert "closed" in closed.reply.lower()

    monkeypatch.setenv("HOSTEL_NOW", "2026-11-24T08:30:00")
    before = read_json(MENU_FILE)
    sold_out = Session.start().ask("Order a masala omelette to my room.", [])
    assert sold_out.approvals == []
    assert "out of stock" in sold_out.reply.lower()
    assert read_json(MENU_FILE) == before


def test_session_remembers_the_previous_turn():
    session = Session.start()
    first = session.ask("Is the kitchen open now?")
    second = session.ask("and what's on the menu?")
    humans = [message.content for message in second.messages if isinstance(message, HumanMessage)]
    assert humans == ["Is the kitchen open now?", "and what's on the menu?"]
    assert "open" in first.reply.lower()
    instructions = []
    seen_second = False
    for message in second.messages:
        if isinstance(message, HumanMessage) and message.content.startswith("and "):
            seen_second = True
        if seen_second and isinstance(message, AIMessage):
            for call in message.tool_calls:
                instructions.append(call["args"]["instruction"])
    assert any("Is the kitchen open now?" in text for text in instructions)
    assert "Veg Sandwich" in second.reply


def test_specialist_loop_stops_on_the_tool_cap():
    raw = run_specialist(
        "booking",
        "When is my checkout, and which room am I in?",
        guest_in_room("305"),
        model=LoopingChatModel(tool_name="get_my_booking"),
        limiter=CallLimiter("booking", max_model_calls=4, max_tool_calls=2),
    )
    data = json.loads(raw)
    assert data["status"] == "limit"
    assert "Stopped: booking reached the tool-call limit for get_my_booking" in data["message"]


def test_payloads_do_not_claim_success_on_refusal():
    turn = Session.start(guest_in_room("101")).ask("Check me out tomorrow at 7 am.", [])
    assert turn.approvals == []
    payloads = _specialist_payloads(turn.messages)
    assert payloads[-1]["status"] == "refused"
    assert "confirmed" not in turn.reply.lower()
