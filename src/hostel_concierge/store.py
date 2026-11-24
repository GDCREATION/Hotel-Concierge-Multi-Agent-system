import json
from typing import Any

from hostel_concierge.paths import data_dir

GUESTS_FILE = "guests_bookings.json"
MENU_FILE = "menu.json"
HOURS_FILE = "kitchen_hours.json"
ORDERS_FILE = "orders.json"


def read_json(name: str) -> Any:
    path = data_dir() / name
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(name: str, payload: Any) -> None:
    path = data_dir() / name
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
