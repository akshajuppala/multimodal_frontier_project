"""Daily routine skill — log and query the user's activities throughout the day."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from langchain_core.tools import tool

from src.state.store import get_store


@tool
def daily_routine(action: str = "today", activity: str = "", location: str = "", hours_back: float = 24.0) -> str:
    """Query or update the user's daily routine log.

    Actions:
      - "today": get a summary of today's activities so far
      - "log": record a new activity (requires activity, optional location)
      - "history": get activities from the last N hours (set hours_back)
    """
    store = get_store()

    if action == "log":
        if not activity:
            return "Please provide an activity description to log."
        store.log_routine(activity, location or None)
        return f"Logged activity: {activity}" + (f" at {location}" if location else "")

    if action == "history":
        entries = store.get_routine_range(hours_back)
        if not entries:
            return f"No activities recorded in the last {hours_back} hours."
        lines = [f"- {e['time']}: {e['activity']}" + (f" ({e['location']})" if e.get("location") else "") for e in entries]
        return f"Activities (last {hours_back}h):\n" + "\n".join(lines)

    # Default: today
    entries = store.get_routine_today()
    if not entries:
        return "No activities recorded today yet."
    lines = [f"- {e['time']}: {e['activity']}" + (f" ({e['location']})" if e.get("location") else "") for e in entries]
    return "Today's activities:\n" + "\n".join(lines)
