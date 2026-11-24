import json

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from hostel_concierge.reference import SCENARIOS
from hostel_concierge.session import Session
from hostel_concierge.store import GUESTS_FILE, MENU_FILE, ORDERS_FILE, read_json


def _run(scenario_id: str):
    scenario = next(item for item in SCENARIOS if item["id"] == scenario_id)
    session = Session.start()
    turns = []
    decisions = list(scenario["decisions"])
    for prompt in scenario["prompts"]:
        turns.append(session.ask(prompt, decisions))
    assert decisions == []
    return turns


def _tool_names(turn) -> list[str]:
    names = []
    for message in turn.messages:
        if isinstance(message, AIMessage):
            names.extend(call["name"] for call in message.tool_calls)
    return names


def test_r1_booking_read():
    turn = _run("R1")[0]
    assert turn.approvals == []
    assert _tool_names(turn) == ["call_booking_specialist"]
    assert "305" in turn.reply
    assert "2026-11-26" in turn.reply
    payload = json.loads(next(message.content for message in turn.messages if isinstance(message, ToolMessage)))
    assert payload["tool_trace"][0]["tool"] == "get_my_booking"


def test_r2_checkout_approval():
    turn = _run("R2")[0]
    assert turn.approvals[0]["proposal"]["room"] == "305"
    assert "confirmed" in turn.reply.lower()
    guest = next(row for row in read_json(GUESTS_FILE) if row["room"] == "305")
    assert guest["status"] == "checked-out"


def test_r3_order_approval():
    turn = _run("R3")[0]
    assert turn.approvals[0]["tool"] == "place_room_order"
    assert turn.approvals[0]["proposal"]["room"] == "305"
    assert "confirmed" in turn.reply.lower()
    menu = {item["name"]: item["stock"] for item in read_json(MENU_FILE)}
    assert menu["Veg Sandwich"] == 11
    assert read_json(ORDERS_FILE)[0]["room"] == "305"


def test_r4_follow_up_uses_session_memory():
    first, second = _run("R4")
    assert "open" in first.reply.lower()
    humans = [message.content for message in second.messages if isinstance(message, HumanMessage)]
    assert humans == ["Is the kitchen open now?", "and what's on the menu?"]
    assert "Veg Sandwich" in second.reply
    assert "Peanut Chikki" in second.reply


def test_r5_both_specialists_one_reply():
    turn = _run("R5")[0]
    assert _tool_names(turn)[:2] == ["call_booking_specialist", "call_kitchen_specialist"]
    assert len(turn.approvals) == 1
    assert "confirmed" in turn.reply.lower()
    assert "kitchen is open" in turn.reply.lower()


def test_r6_other_room_blocked():
    turn = _run("R6")[0]
    assert "blocked" in turn.reply.lower()
    assert "204" in turn.reply
    assert "Liam" not in turn.reply
    payload = json.loads(next(message.content for message in turn.messages if isinstance(message, ToolMessage)))
    assert payload["status"] == "blocked"
    assert payload["tool_trace"] == []
    other = next(row for row in read_json(GUESTS_FILE) if row["room"] == "204")
    assert other["status"] == "checked-in"


def test_r7_out_of_scope():
    turn = _run("R7")[0]
    assert turn.approvals == []
    assert _tool_names(turn) == []
    assert "weather" in turn.reply.lower()
    assert "booking" in turn.reply.lower()
