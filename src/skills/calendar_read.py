import json
from pathlib import Path

from railtracks import function_node

CALENDAR_PATH = "data/calendar.json"


def read_calendar_file(path: str = CALENDAR_PATH) -> list[dict]:
    """Read all events from the calendar file."""
    cal_path = Path(path)
    if not cal_path.exists():
        return []
    with open(cal_path) as f:
        data = json.load(f)
    return data.get("events", [])


@function_node
def calendar_read(date_filter: str = "") -> str:
    """Read upcoming events from the calendar. Optionally filter by date prefix (e.g. '2026-03-29')."""
    events = read_calendar_file()
    if date_filter:
        events = [e for e in events if e["datetime"].startswith(date_filter)]
    if not events:
        return "No upcoming events found."
    lines = []
    for e in events:
        lines.append(f"- {e['title']} at {e['datetime']}: {e['description']}")
    return "\n".join(lines)
