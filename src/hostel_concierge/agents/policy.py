"""Deterministic routing used by the scripted model.

A live model replaces this module. The graph, allow-lists, and approval gate stay the same.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hostel_concierge.store import MENU_FILE, read_json

_OUT_OF_SCOPE = ("weather", "temperature outside", "news", "joke", "football", "president")


@dataclass
class Decision:
    kind: str
    message: str = ""
    specialists: list[str] = field(default_factory=list)
    instructions: dict[str, str] = field(default_factory=dict)
    follow_up: str = ""


def match_item_names(text: str) -> list[str]:
    lowered = text.casefold()
    found: list[str] = []
    menu = sorted(read_json(MENU_FILE), key=lambda item: len(item["name"]), reverse=True)
    for item in menu:
        name = item["name"]
        if name.casefold() in lowered and name not in found:
            found.append(name)
    return found


def extract_when(text: str) -> str | None:
    patterns = (
        r"\btomorrow\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
        r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\s+tomorrow\b",
        r"\btomorrow\s+morning\b",
        r"\btomorrow\s+evening\b",
        r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return None


def booking_mode(text: str) -> str:
    lowered = text.lower()
    action_out = bool(
        re.search(
            r"check me out|check-me-out|check out at|check out tomorrow|i check out|want to check out",
            lowered,
        )
    )
    action_in = bool(
        re.search(
            r"check me in|check-me-in|check in at|check in tomorrow|i check in|want to check in",
            lowered,
        )
    )
    if action_in and action_out:
        return "unclear-action"
    if action_out:
        return "check-out"
    if action_in:
        return "check-in"
    return "read"


def kitchen_mode(text: str) -> str:
    names = match_item_names(text)
    lowered = text.lower()
    order_verb = bool(re.search(r"\b(order|bring|send)\b", lowered))
    get_item = bool(names) and bool(re.search(r"\b(get|have|want)\b", lowered))
    if order_verb or get_item:
        return "order" if names else "ask-items"
    return "status"


def _corpus(text: str, history: list[str]) -> str:
    if history and re.match(r"(?i)(and|also)\b", text.strip()):
        return history[-1] + "\n" + text
    return text


def has_booking_intent(text: str, history: list[str]) -> bool:
    blob = _corpus(text, history)
    if booking_mode(blob) != "read":
        return True
    return bool(
        re.search(
            r"when is my checkout|checkout date|which room|what room am i|\bbooking\b|booking status|check-in date",
            blob,
            re.IGNORECASE,
        )
    )


def has_kitchen_intent(text: str, history: list[str]) -> bool:
    blob = _corpus(text, history)
    if match_item_names(blob):
        return True
    return bool(
        re.search(
            r"\b(kitchen|menu|order|breakfast|lunch|dinner|hungry|food|snack|allergen)\b",
            blob,
            re.IGNORECASE,
        )
    )


def instruction_for(specialist: str, text: str, history: list[str]) -> str:
    focus = {
        "booking": "You handle only this guest's booking. Ignore food and menu details.",
        "kitchen": (
            "You handle only the kitchen: menu, hours, and orders to this guest's own room. "
            "Ignore check-in and checkout."
        ),
    }[specialist]
    lines = [f"Guest: {turn}" for turn in [*history, text]]
    return (
        "The app already knows who the guest is. Do not ask for a guest id or room number. "
        "Do not use any room other than the one bound by the app.\n"
        f"{focus}\n\n"
        "Complete instruction (you cannot see the rest of the chat):\n" + "\n".join(lines)
    )


def classify(text: str, history: list[str] | None = None) -> Decision:
    history = list(history or [])
    booking = has_booking_intent(text, history)
    kitchen = has_kitchen_intent(text, history)
    if not booking and not kitchen:
        lowered = text.lower()
        if any(cue in lowered for cue in _OUT_OF_SCOPE):
            if "weather" in lowered or "temperature" in lowered:
                return Decision(
                    "decline",
                    "I can only help with your Sunrise Hostel booking and kitchen orders, so I can't look up the weather.",
                )
            return Decision(
                "decline",
                "I can only help with your Sunrise Hostel booking and kitchen orders.",
            )
        return Decision(
            "decline",
            "I can only help with your Sunrise Hostel booking and kitchen orders. Tell me if you need your booking or the kitchen.",
        )

    corpus = _corpus(text, history)
    mode = booking_mode(corpus) if booking else "read"
    if booking and mode == "unclear-action":
        return Decision("clarify", "Do you want to check in or check out?")
    if booking and mode in {"check-in", "check-out"} and not extract_when(corpus):
        return Decision("clarify", f"What time should I use for {mode}?")

    follow_up = ""
    specialists: list[str] = []
    if booking:
        specialists.append("booking")
    if kitchen:
        kmode = kitchen_mode(corpus)
        if kmode == "ask-items":
            follow_up = "What would you like to order? Tell me the item names."
            if not booking:
                return Decision("clarify", follow_up)
        else:
            specialists.append("kitchen")
    instructions = {name: instruction_for(name, text, history) for name in specialists}
    return Decision("delegate", specialists=specialists, instructions=instructions, follow_up=follow_up)
