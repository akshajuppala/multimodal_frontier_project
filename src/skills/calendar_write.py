import json
import uuid
from pathlib import Path

import railtracks as rt

CALENDAR_PATH = "data/calendar.json"


def write_calendar_file(path: str = CALENDAR_PATH, event: dict = None) -> None:
    """Write or update an event in the calendar file."""
    cal_path = Path(path)
    if cal_path.exists():
        with open(cal_path) as f:
            data = json.load(f)
    else:
        data = {"events": []}

    existing_ids = {e["id"]: i for i, e in enumerate(data["events"])}
    if event["id"] in existing_ids:
        data["events"][existing_ids[event["id"]]] = event
    else:
        data["events"].append(event)

    with open(cal_path, "w") as f:
        json.dump(data, f, indent=2)


@rt.function_node
def calendar_write(title: str, datetime_str: str, description: str = "", reminder_minutes_before: int = 15) -> str:
    """Add a new event to the calendar. Provide a title, datetime (ISO format), optional description, and reminder time in minutes.

    Args:
        title (str): The title of the event.
        datetime_str (str): The datetime of the event in ISO format.
        description (str): Optional description of the event.
        reminder_minutes_before (int): Minutes before the event to send a reminder.
    """
    event = {
        "id": f"evt-{uuid.uuid4().hex[:8]}",
        "title": title,
        "datetime": datetime_str,
        "description": description,
        "reminder_minutes_before": reminder_minutes_before,
    }
    write_calendar_file(event=event)
    return f"Event '{title}' added for {datetime_str}."
