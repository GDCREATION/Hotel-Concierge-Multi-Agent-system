import argparse

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from hostel_concierge.session import Session, guest_in_room


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Sunrise Hostel concierge")
    parser.add_argument("--room", default="305", help="Logged-in guest room. The guest does not type this.")
    parser.add_argument(
        "--demo-limit",
        action="store_true",
        help="Run the looping-agent demo that stops on a call limit.",
    )
    args = parser.parse_args()
    if args.demo_limit:
        from hostel_concierge.demo_limit import main as demo_main

        demo_main()
        return

    console = Console()
    guest = guest_in_room(args.room)
    session = Session.start(guest)
    console.print(
        Panel(
            f"Signed in as room {guest.room} ({guest.guest_id}). "
            "Ask about your booking or the kitchen. Type /quit to leave.\n"
            "Risky actions pause until you approve or reject them.",
            title="Sunrise Hostel",
        )
    )
    while True:
        text = console.input("[bold]You:[/bold] ").strip()
        if not text:
            continue
        if text in {"/quit", "quit", "exit"}:
            break
        turn = session.ask(text, interactive=True)
        console.print(Panel(turn.reply, title="Concierge"))


if __name__ == "__main__":
    main()
