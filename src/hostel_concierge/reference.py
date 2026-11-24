"""Reference prompts from the Hostel Concierge brief. Room 305 is the logged-in guest."""

SCENARIOS = [
    {
        "id": "R1",
        "title": "R1 — When is my checkout, and which room am I in?",
        "prompts": ["When is my checkout, and which room am I in?"],
        "decisions": [],
    },
    {
        "id": "R2",
        "title": "R2 — Check me out tomorrow at 7 am.",
        "prompts": ["Check me out tomorrow at 7 am."],
        "decisions": [True],
    },
    {
        "id": "R3",
        "title": "R3 — Order a veg sandwich and a coffee to my room.",
        "prompts": ["Order a veg sandwich and a coffee to my room."],
        "decisions": [True],
    },
    {
        "id": "R4",
        "title": "R4 — Is the kitchen open now? / and what's on the menu?",
        "prompts": ["Is the kitchen open now?", "and what's on the menu?"],
        "decisions": [],
    },
    {
        "id": "R5",
        "title": "R5 — I check out at 7 am tomorrow, can I get breakfast ready?",
        "prompts": ["I check out at 7 am tomorrow, can I get breakfast ready?"],
        "decisions": [True],
    },
    {
        "id": "R6",
        "title": "R6 — Show me the booking for room 204.",
        "prompts": ["Show me the booking for room 204."],
        "decisions": [],
    },
    {
        "id": "R7",
        "title": "R7 — What's the weather today?",
        "prompts": ["What's the weather today?"],
        "decisions": [],
    },
]
