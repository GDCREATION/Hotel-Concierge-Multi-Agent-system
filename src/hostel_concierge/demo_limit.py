"""Show a tool-calling loop stopped by the coded limit, not by the prompt."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from hostel_concierge.agents.llm import LoopingChatModel
from hostel_concierge.agents.orchestrator import build_app
from hostel_concierge.agents.specialist import run_specialist
from hostel_concierge.paths import repo_root
from hostel_concierge.runtime_state import reset_runtime
from hostel_concierge.safety.limits import CallLimiter
from hostel_concierge.session import Session, guest_in_room
from hostel_concierge.tracing import render_turns


def specialist_loop() -> str:
    guest = guest_in_room("305")
    limiter = CallLimiter("booking", max_model_calls=4, max_tool_calls=2)
    model = LoopingChatModel(tool_name="get_my_booking")
    return run_specialist(
        "booking",
        "When is my checkout, and which room am I in?",
        guest,
        model=model,
        limiter=limiter,
    )


def orchestrator_loop():
    app = build_app(
        orchestrator_model=LoopingChatModel(
            tool_name="call_booking_specialist",
            tool_args={"instruction": "When is my checkout, and which room am I in?"},
        ),
        limit_overrides={"orchestrator": {"max_model_calls": 3, "max_tool_calls": 1}},
    )
    session = Session.start(guest_in_room("305"), app=app)
    return session.ask("Please keep checking.")


def write_limit_trace(output_dir: Path | None = None) -> Path:
    root = repo_root()
    output = output_dir or (root / "traces")
    output.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("HOSTEL_NOW", "2026-11-24T08:30:00")
    os.environ["HOSTEL_MODEL"] = "scripted"
    workspace = Path(tempfile.mkdtemp(prefix="hostel-limit-"))
    data = workspace / "data"
    shutil.copytree(root / "data", data)
    os.environ["HOSTEL_DATA_DIR"] = str(data)
    reset_runtime()
    specialist = specialist_loop()
    reset_runtime()
    turn = orchestrator_loop()
    body = "\n".join(
        [
            "# Limit stop",
            "",
            "A looping model keeps requesting the same tool. The cap in config/code stops it.",
            "",
            "## Specialist tool limit",
            "",
            "Booking specialist, max 2 calls to `get_my_booking`.",
            "",
            specialist,
            "",
            "## Orchestrator tool and model limit",
            "",
            "Orchestrator max_tool_calls=1 for each specialist tool, max_model_calls=3.",
            "",
            turn.reply,
            "",
        ]
    )
    rendered = render_turns(
        "Limit stop — orchestrator loop",
        ["Please keep checking."],
        [turn],
        clock=os.environ.get("HOSTEL_NOW", ""),
        room="305",
    )
    path = output / "limit-stop.md"
    path.write_text(body + "\n" + rendered, encoding="utf-8")
    return path


def main() -> None:
    path = write_limit_trace()
    print(path.read_text(encoding="utf-8"))
    print(f"\nWrote {path}")


if __name__ == "__main__":
    main()
