"""Streamlit demo for the guest concierge flow.

Run from the repo root:

    export PYTHONPATH=src
    export HOSTEL_NOW=2026-11-24T08:30:00
    export HOSTEL_MODEL=bedrock
    .venv/bin/streamlit run src/hostel_concierge/ui/app.py
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from hostel_concierge.demo_limit import orchestrator_loop, specialist_loop
from hostel_concierge.reference import SCENARIOS
from hostel_concierge.runtime_state import reset_runtime
from hostel_concierge.session import Session, guest_in_room, inspect_turn

SCENARIO_HINTS = {
    "R1": "Booking read — checkout date and room from GuestContext.",
    "R2": "Checkout proposal — pauses for Approve/Reject before any write.",
    "R3": "Room order — pauses for approval; confirmed only after commit.",
    "R4": "Two kitchen turns — memory carries the first question into the second.",
    "R5": "Both specialists — checkout approval, then kitchen hours/menu (no invented dish).",
    "R6": "Other-room block — blocked before tools; empty tool trace.",
    "R7": "Out of scope — weather; no tools.",
    "LIMIT": "Looping model stopped by coded caps (uses a scripted looping model).",
}


def _ensure_env() -> None:
    load_dotenv()
    os.environ.setdefault("HOSTEL_NOW", "2026-11-24T08:30:00")
    os.environ.setdefault("HOSTEL_MODEL", "bedrock")


def _new_session() -> Session:
    reset_runtime()
    return Session.start(guest_in_room("305"))


def _init_state() -> None:
    if "session" not in st.session_state:
        st.session_state.session = _new_session()
    if "chat" not in st.session_state:
        st.session_state.chat = []
    if "pending" not in st.session_state:
        st.session_state.pending = None
    if "prior_approvals" not in st.session_state:
        st.session_state.prior_approvals = []
    if "inspector" not in st.session_state:
        st.session_state.inspector = None
    if "scenario_hint" not in st.session_state:
        st.session_state.scenario_hint = ""
    if "queued_prompt" not in st.session_state:
        st.session_state.queued_prompt = None
    if "limit_output" not in st.session_state:
        st.session_state.limit_output = None


def _reset() -> None:
    st.session_state.session = _new_session()
    st.session_state.chat = []
    st.session_state.pending = None
    st.session_state.prior_approvals = []
    st.session_state.inspector = None
    st.session_state.scenario_hint = ""
    st.session_state.queued_prompt = None
    st.session_state.limit_output = None


def _record_assistant(turn) -> None:
    st.session_state.inspector = inspect_turn(turn)
    if turn.pending:
        st.session_state.pending = turn.approvals[-1]
        st.session_state.prior_approvals = list(turn.approvals)
        st.session_state.chat.append(
            {
                "role": "assistant",
                "content": "Approval needed before anything is saved. Use Approve or Reject below.",
            }
        )
        return
    st.session_state.pending = None
    st.session_state.prior_approvals = list(turn.approvals)
    st.session_state.chat.append({"role": "assistant", "content": turn.reply or "(empty reply)"})


def _send(text: str) -> None:
    text = text.strip()
    if not text or st.session_state.pending:
        return
    st.session_state.chat.append({"role": "user", "content": text})
    try:
        with st.spinner("Concierge is working…"):
            turn = st.session_state.session.ask_until_interrupt(text)
        _record_assistant(turn)
    except Exception as exc:  # noqa: BLE001 - show Bedrock/AWS errors in the UI
        st.session_state.chat.append(
            {"role": "assistant", "content": f"Error talking to the model: {exc}"}
        )
        st.session_state.inspector = None


def _decide(approved: bool) -> None:
    if not st.session_state.pending:
        return
    try:
        with st.spinner("Applying your decision…"):
            turn = st.session_state.session.resume(
                approved,
                prior_approvals=st.session_state.prior_approvals,
            )
        # Replace the “approval needed” placeholder with the real outcome path
        if st.session_state.chat and st.session_state.chat[-1]["role"] == "assistant":
            st.session_state.chat.pop()
        _record_assistant(turn)
    except Exception as exc:  # noqa: BLE001
        st.session_state.chat.append(
            {"role": "assistant", "content": f"Error resuming after approval: {exc}"}
        )


def _run_limit_demo() -> None:
    st.session_state.scenario_hint = SCENARIO_HINTS["LIMIT"]
    try:
        with st.spinner("Running limit-stop demo (scripted looping model)…"):
            reset_runtime()
            specialist = specialist_loop()
            reset_runtime()
            turn = orchestrator_loop()
        st.session_state.limit_output = {
            "specialist": specialist,
            "orchestrator": turn.reply,
        }
        st.session_state.inspector = inspect_turn(turn)
        st.session_state.chat.append(
            {
                "role": "user",
                "content": "[Limit stop demo] Please keep checking.",
            }
        )
        st.session_state.chat.append(
            {
                "role": "assistant",
                "content": (
                    "### Specialist tool limit\n\n"
                    f"{specialist}\n\n"
                    "### Orchestrator stop\n\n"
                    f"{turn.reply}"
                ),
            }
        )
        # Limit demo uses its own looping app; restore a normal Bedrock session afterward.
        st.session_state.session = _new_session()
        st.session_state.pending = None
        st.session_state.prior_approvals = []
    except Exception as exc:  # noqa: BLE001
        st.session_state.chat.append(
            {"role": "assistant", "content": f"Limit demo failed: {exc}"}
        )


def _sidebar() -> None:
    guest = st.session_state.session.guest
    st.sidebar.markdown("## Sunrise Hostel")
    st.sidebar.info(f"Signed in as **room {guest.room}** (`{guest.guest_id}`)")
    st.sidebar.caption(
        "Guest id and room come from the app. Do not type another room to “switch”."
    )
    st.sidebar.markdown("### Scenarios")
    for scenario in SCENARIOS:
        label = scenario["id"]
        if st.sidebar.button(scenario["title"], key=f"sc_{label}", use_container_width=True):
            st.session_state.scenario_hint = SCENARIO_HINTS.get(label, "")
            prompts = scenario["prompts"]
            # Queue the first prompt; for R4 the second is typed/sent after the first reply
            st.session_state.queued_prompt = prompts[0]
            if len(prompts) > 1:
                st.session_state.scenario_hint += (
                    f" After the first reply, send: “{prompts[1]}”"
                )
            st.rerun()
    if st.sidebar.button("Limit stop demo", key="sc_limit", use_container_width=True):
        _run_limit_demo()
        st.rerun()
    st.sidebar.markdown("---")
    if st.sidebar.button("Reset session", use_container_width=True):
        _reset()
        st.rerun()
    if st.session_state.scenario_hint:
        st.sidebar.markdown("### What to expect")
        st.sidebar.write(st.session_state.scenario_hint)
    st.sidebar.markdown("---")
    st.sidebar.caption(
        f"Model: `{os.environ.get('HOSTEL_MODEL', 'bedrock')}` · "
        f"Clock: `{os.environ.get('HOSTEL_NOW', '')}`"
    )


def _approval_card(payload: dict[str, Any]) -> None:
    proposal = payload.get("proposal") or {}
    st.warning("Approval needed — nothing is saved until you approve.")
    st.markdown(payload.get("message") or "Approve this action?")
    cols = st.columns(2)
    cols[0].markdown(f"**Agent:** `{payload.get('agent')}`")
    cols[1].markdown(f"**Tool:** `{payload.get('tool')}`")
    if proposal:
        st.markdown(
            f"Proposal `{proposal.get('id')}` for room **{proposal.get('room')}**."
        )
        if proposal.get("items"):
            st.markdown("Items: " + ", ".join(str(item) for item in proposal["items"]))
        when = proposal.get("when") or proposal.get("checkout_at") or proposal.get("requested_time")
        if when:
            st.markdown(f"When: `{when}`")
        if proposal.get("action"):
            st.markdown(f"Action: `{proposal['action']}` → `{proposal.get('to_status')}`")
    left, right = st.columns(2)
    if left.button("Approve", type="primary", use_container_width=True):
        _decide(True)
        st.rerun()
    if right.button("Reject", use_container_width=True):
        _decide(False)
        st.rerun()


def _inspector_panel() -> None:
    st.markdown("### Turn inspector")
    snapshot = st.session_state.inspector
    if not snapshot:
        st.caption("Send a message to see specialists and tools for the last turn.")
        return
    st.markdown(f"**Status:** `{snapshot['status']}`")
    specialists = snapshot.get("specialists") or []
    tools = snapshot.get("tools") or []
    st.markdown(
        "**Specialists:** "
        + (", ".join(f"`{name}`" for name in specialists) if specialists else "_none_")
    )
    st.markdown(
        "**Tools:** " + (", ".join(f"`{name}`" for name in tools) if tools else "_none_")
    )
    pending = snapshot.get("pending")
    if pending:
        st.markdown(
            f"**Pending:** `{pending.get('tool')}` on `{pending.get('agent')}` — "
            "nothing written yet."
        )


def main() -> None:
    _ensure_env()
    st.set_page_config(page_title="Sunrise Hostel Concierge", layout="wide")
    _init_state()
    _sidebar()

    st.title("Sunrise Hostel Concierge")
    st.caption("Demo UI — orchestrator → specialists → MCP tools, with coded approval pauses.")

    chat_col, inspect_col = st.columns((2, 1))
    with chat_col:
        for message in st.session_state.chat:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        if st.session_state.pending:
            _approval_card(st.session_state.pending)
        queued = st.session_state.queued_prompt
        if queued and not st.session_state.pending:
            st.session_state.queued_prompt = None
            _send(queued)
            st.rerun()
        prompt = st.chat_input(
            "Ask about your booking or the kitchen…",
            disabled=bool(st.session_state.pending),
        )
        if prompt:
            _send(prompt)
            st.rerun()
    with inspect_col:
        _inspector_panel()
        if st.session_state.limit_output:
            with st.expander("Limit demo raw output"):
                st.code(st.session_state.limit_output["specialist"], language="text")
                st.code(st.session_state.limit_output["orchestrator"], language="text")


if __name__ == "__main__":
    main()
