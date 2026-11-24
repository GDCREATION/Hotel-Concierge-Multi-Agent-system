from hostel_concierge.agents.policy import classify


def test_reference_routing():
    r1 = classify("When is my checkout, and which room am I in?")
    assert r1.specialists == ["booking"]

    r2 = classify("Check me out tomorrow at 7 am.")
    assert r2.specialists == ["booking"]

    r3 = classify("Order a veg sandwich and a coffee to my room.")
    assert r3.specialists == ["kitchen"]

    r5 = classify("I check out at 7 am tomorrow, can I get breakfast ready?")
    assert r5.specialists == ["booking", "kitchen"]

    r6 = classify("Show me the booking for room 204.")
    assert r6.specialists == ["booking"]
    assert "room 204" in r6.instructions["booking"]

    r7 = classify("What's the weather today?")
    assert r7.kind == "decline"
    assert "weather" in r7.message.lower()


def test_missing_details_ask_instead_of_guessing():
    checkout = classify("Check me out.")
    assert checkout.kind == "clarify"
    assert "time" in checkout.message.lower()

    order = classify("Can you order something?")
    assert order.kind == "clarify"
    assert "item" in order.message.lower()


def test_follow_up_inherits_the_previous_guest_turn():
    decision = classify("and what's on the menu?", ["Is the kitchen open now?"])
    assert decision.specialists == ["kitchen"]
    instruction = decision.instructions["kitchen"]
    assert "Is the kitchen open now?" in instruction
    assert "and what's on the menu?" in instruction
