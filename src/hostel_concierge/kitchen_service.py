from __future__ import annotations

from datetime import datetime, time
from uuid import uuid4

from hostel_concierge.clock import now as clock_now
from hostel_concierge.models import GuestContext
from hostel_concierge.runtime_state import (
    committed_result,
    get_proposal,
    is_approved,
    mark_committed,
    save_proposal,
)
from hostel_concierge.store import HOURS_FILE, MENU_FILE, ORDERS_FILE, read_json, write_json

_MEAL_ORDER = ("breakfast", "lunch", "dinner")


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def kitchen_open(moment: datetime | None = None) -> dict:
    moment = moment or clock_now()
    hours = read_json(HOURS_FILE)
    current = moment.time().replace(second=0, microsecond=0)
    for meal in _MEAL_ORDER:
        window = hours[meal]
        if _parse_time(window["open"]) <= current < _parse_time(window["close"]):
            return {
                "open": True,
                "meal": meal,
                "open_time": window["open"],
                "close_time": window["close"],
            }
    for meal in _MEAL_ORDER:
        window = hours[meal]
        if current < _parse_time(window["open"]):
            return {
                "open": False,
                "meal": None,
                "next_meal": meal,
                "next_open": window["open"],
            }
    breakfast = hours["breakfast"]
    return {
        "open": False,
        "meal": None,
        "next_meal": "breakfast",
        "next_open": f"{breakfast['open']} tomorrow",
    }


def _menu_lines(menu: list[dict]) -> str:
    lines = []
    for item in menu:
        allergens = ", ".join(item["allergens"]) if item["allergens"] else "none"
        lines.append(
            f"- {item['name']} (Rs {item['price']}, stock {item['stock']}, allergens: {allergens})"
        )
    return "\n".join(lines)


def _hours_sentence(info: dict) -> str:
    if info["open"]:
        return (
            f"The kitchen is open now for {info['meal']} "
            f"({info['open_time']}-{info['close_time']})."
        )
    return (
        f"The kitchen is closed now. Next is {info['next_meal']} at {info['next_open']}."
    )


def get_menu_and_kitchen_status() -> dict:
    menu = read_json(MENU_FILE)
    info = kitchen_open()
    message = _hours_sentence(info) + "\n" + _menu_lines(menu)
    return {"status": "ok", "kitchen": info, "menu": menu, "message": message}


def _find_item(menu: list[dict], name: str) -> dict | None:
    target = name.casefold().strip()
    for item in menu:
        if item["name"].casefold() == target:
            return item
    return None


def propose_order(guest: GuestContext, items: list[str]) -> dict:
    names = [name.strip() for name in items if name and name.strip()]
    if not names:
        return {
            "status": "needs_detail",
            "message": "What would you like to order? I need the item names.",
        }
    info = kitchen_open()
    if not info["open"]:
        return {
            "status": "refused",
            "code": "kitchen_closed",
            "message": "The kitchen is closed right now, so I can't place that order.",
        }
    menu = read_json(MENU_FILE)
    resolved: list[dict] = []
    seen: set[str] = set()
    for name in names:
        item = _find_item(menu, name)
        if item is None:
            return {
                "status": "refused",
                "code": "not_on_menu",
                "message": f"I can't order {name} because it isn't on the menu.",
            }
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        if int(item["stock"]) <= 0:
            return {
                "status": "refused",
                "code": "out_of_stock",
                "message": f"{item['name']} is out of stock, so I didn't place the order.",
            }
        resolved.append(item)
    total = sum(int(item["price"]) for item in resolved)
    allergens = sorted({allergen for item in resolved for allergen in item["allergens"]})
    proposal = {
        "id": f"order_{uuid4().hex[:10]}",
        "type": "order",
        "guest_id": guest.guest_id,
        "room": guest.room,
        "items": [
            {"id": item["id"], "name": item["name"], "price": item["price"], "qty": 1}
            for item in resolved
        ],
        "total": total,
        "allergens": allergens,
    }
    save_proposal(proposal)
    item_text = ", ".join(item["name"] for item in resolved)
    warning = " This order contains peanuts." if "peanuts" in allergens else ""
    return {
        "status": "pending_approval",
        "tool": "place_room_order",
        "proposal": proposal,
        "message": (
            f"Proposed order for room {guest.room}: {item_text}. Total Rs {total}.{warning} "
            "Nothing has been sent to the kitchen yet."
        ),
    }


def commit(proposal_id: str) -> dict:
    existing = committed_result(proposal_id)
    if existing is not None:
        return existing
    if not is_approved(proposal_id):
        return {
            "status": "error",
            "code": "approval_missing",
            "commit_tool": "commit_room_order",
            "message": "This order was not approved, so nothing was sent to the kitchen.",
        }
    proposal = get_proposal(proposal_id)
    if proposal is None:
        return {
            "status": "error",
            "code": "proposal_missing",
            "commit_tool": "commit_room_order",
            "message": "That order proposal is no longer available, so nothing was sent.",
        }
    info = kitchen_open()
    if not info["open"]:
        return {
            "status": "refused",
            "code": "kitchen_closed",
            "commit_tool": "commit_room_order",
            "message": "The kitchen is closed right now, so I can't place that order.",
        }
    menu = read_json(MENU_FILE)
    by_id = {item["id"]: item for item in menu}
    for line in proposal["items"]:
        item = by_id.get(line["id"])
        if item is None or int(item["stock"]) < int(line["qty"]):
            name = line["name"]
            return {
                "status": "refused",
                "code": "out_of_stock",
                "commit_tool": "commit_room_order",
                "message": f"{name} is out of stock, so I didn't place the order.",
            }
    for line in proposal["items"]:
        by_id[line["id"]]["stock"] = int(by_id[line["id"]]["stock"]) - int(line["qty"])
    write_json(MENU_FILE, menu)
    orders = read_json(ORDERS_FILE)
    orders.append(
        {
            "id": proposal["id"],
            "guest_id": proposal["guest_id"],
            "room": proposal["room"],
            "items": proposal["items"],
            "total": proposal["total"],
            "status": "placed",
        }
    )
    write_json(ORDERS_FILE, orders)
    item_text = ", ".join(line["name"] for line in proposal["items"])
    result = {
        "status": "completed",
        "commit_tool": "commit_room_order",
        "proposal": proposal,
        "message": (
            f"Order confirmed for room {proposal['room']}: {item_text}. "
            f"Total Rs {proposal['total']}. The kitchen has the order."
        ),
    }
    mark_committed(proposal_id, result)
    return result
