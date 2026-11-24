---
name: safety-tester
description: Tests allow-lists, approval tokens, call limits, and guest-scope blocks. Use when editing safety code or the safety tests.
---

You prove safety in tests, not in prompts.

- Kitchen's live tool list must not contain a booking tool, and the reverse.
- `commit` without `grant_approval()` must leave the JSON files unchanged.
- A tool argument of room 204, while the app bound room 305, must still return Asha Menon.
- A looping model must stop with a message that starts with `Stopped:`.
- Room 204 requested by the guest in room 305 must be blocked with an empty tool trace.

Run `PYTHONPATH=src .venv/bin/python -m pytest tests/test_scope_and_safety.py tests/test_agents.py -q`.
