"""Process-local guest binding and approval tokens.

The model never writes this state. The app binds the guest, and ApprovalGate
adds proposal ids here only after the guest approves.
"""

from __future__ import annotations

import copy
import os
import threading
from typing import Any

from hostel_concierge.models import GuestContext

_lock = threading.Lock()
_guest: GuestContext | None = None
_proposals: dict[str, dict[str, Any]] = {}
_approved: set[str] = set()
_mcp_names: set[str] | None = None


class MissingGuest(RuntimeError):
    pass


def reset_runtime() -> None:
    global _guest, _mcp_names
    with _lock:
        _guest = None
        _proposals.clear()
        _approved.clear()
        _mcp_names = None


def bind_guest(guest: GuestContext) -> None:
    global _guest
    with _lock:
        _guest = guest


def bound_guest() -> GuestContext | None:
    with _lock:
        if _guest is not None:
            return _guest
    guest_id = os.environ.get("HOSTEL_GUEST_ID")
    room = os.environ.get("HOSTEL_ROOM")
    if guest_id and room:
        return GuestContext(guest_id=guest_id, room=room)
    return None


def require_guest() -> GuestContext:
    guest = bound_guest()
    if guest is None:
        raise MissingGuest(
            "No guest is bound. The app must pass GuestContext; the model cannot supply it."
        )
    return guest


def save_proposal(proposal: dict[str, Any]) -> None:
    with _lock:
        _proposals[proposal["id"]] = copy.deepcopy(proposal)


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    with _lock:
        item = _proposals.get(proposal_id)
        if item is None:
            return None
        return copy.deepcopy(item)


def grant_approval(proposal_id: str) -> None:
    """Record a human decision. Commit functions refuse to run without this."""

    with _lock:
        _approved.add(proposal_id)


def is_approved(proposal_id: str) -> bool:
    with _lock:
        return proposal_id in _approved


def mark_committed(proposal_id: str, result: dict[str, Any]) -> None:
    with _lock:
        proposal = _proposals.get(proposal_id)
        if proposal is not None:
            proposal["committed"] = True
            proposal["result"] = copy.deepcopy(result)


def committed_result(proposal_id: str) -> dict[str, Any] | None:
    with _lock:
        proposal = _proposals.get(proposal_id)
        if proposal and proposal.get("committed"):
            return copy.deepcopy(proposal["result"])
        return None


def cache_mcp_names(names: set[str]) -> None:
    global _mcp_names
    _mcp_names = set(names)


def cached_mcp_names() -> set[str] | None:
    if _mcp_names is None:
        return None
    return set(_mcp_names)
