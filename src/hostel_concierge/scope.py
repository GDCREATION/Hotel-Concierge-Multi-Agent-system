import re

_ROOM = re.compile(r"\broom\s*#?\s*(\d+)\b", re.IGNORECASE)


def other_rooms(text: str, own_room: str) -> list[str]:
    """Rooms named in the text that are not the app-bound room."""

    found: list[str] = []
    for room in _ROOM.findall(text):
        if room != str(own_room) and room not in found:
            found.append(room)
    return found


def scope_block_message(own_room: str, other_room: str, agent: str) -> str:
    if agent == "booking":
        return (
            f"Blocked. You are logged in to room {own_room}, so I can only show or change that booking. "
            f"I can't access room {other_room}."
        )
    return (
        f"Blocked. Orders stay on room {own_room}. "
        f"I can't place or look up an order for room {other_room}."
    )
