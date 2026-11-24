"""Run R1–R7 against a fresh copy of the mock data and write markdown traces."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from hostel_concierge.paths import repo_root
from hostel_concierge.reference import SCENARIOS
from hostel_concierge.runtime_state import reset_runtime
from hostel_concierge.session import Session, guest_in_room
from hostel_concierge.tracing import render_turns

CLOCK = "2026-11-24T08:30:00"


def run_prompts(prompts: list[str], decisions: list[bool]):
    session = Session.start(guest_in_room("305"))
    queue = list(decisions)
    turns = []
    for prompt in prompts:
        turns.append(session.ask(prompt, queue))
    if queue:
        raise RuntimeError(f"Unused approval decisions: {queue}")
    return turns


def write_traces(output_dir: Path | None = None) -> Path:
    root = repo_root()
    output = output_dir or (root / "traces")
    output.mkdir(parents=True, exist_ok=True)
    os.environ["HOSTEL_MODEL"] = "scripted"
    os.environ["HOSTEL_NOW"] = CLOCK
    source = root / "data"
    for scenario in SCENARIOS:
        workspace = Path(tempfile.mkdtemp(prefix=f"hostel-{scenario['id']}-"))
        data = workspace / "data"
        shutil.copytree(source, data)
        os.environ["HOSTEL_DATA_DIR"] = str(data)
        reset_runtime()
        turns = run_prompts(scenario["prompts"], scenario["decisions"])
        text = render_turns(
            scenario["title"],
            scenario["prompts"],
            turns,
            clock=CLOCK,
            room="305",
        )
        (output / f"{scenario['id']}.md").write_text(text, encoding="utf-8")
    return output


def main() -> None:
    path = write_traces()
    print(f"Wrote reference traces to {path}")


if __name__ == "__main__":
    main()
