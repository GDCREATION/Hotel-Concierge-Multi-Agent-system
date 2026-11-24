import os
from datetime import datetime


def now() -> datetime:
    """Kitchen 'open now' reads this clock. HOSTEL_NOW freezes demos and tests."""

    raw = os.environ.get("HOSTEL_NOW")
    if raw:
        return datetime.fromisoformat(raw)
    return datetime.now()
