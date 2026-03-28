"""
Daily routine tool — log and query the user's daily activities.

Helps answer questions like "What did I do this morning?" and lets the
agent build a picture of what's normal for the user (so deviations
can trigger gentle check-ins).
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from server.state.models import RoutineEntry
from server.state.store import StateStore


@tool
def daily_routine(action: str = "today", activity: Optional[str] = None, location: Optional[str] = None, hours_back: float = 24.0) -> dict:
    """Query or update the user's daily routine log.

    Args:
        action: One of "today" (get today's routine), "log" (record an activity), or "history" (get past routine).
        activity: Required when action is "log". Description of what the user is doing.
        location: Optional location for "log" action.
        hours_back: How many hours of history for "history" action. Defaults to 24.

    Returns:
        Routine entries or confirmation of logging.
    """
    store = StateStore()
    try:
        if action == "log":
            if not activity:
                return {"error": "activity is required for 'log' action"}
            entry = RoutineEntry(
                timestamp=datetime.utcnow(),
                activity=activity,
                location=location,
            )
            entry_id = store.log_routine(entry)
            return {
                "logged": True,
                "id": entry_id,
                "activity": activity,
                "location": location,
                "timestamp": entry.timestamp.isoformat(),
            }

        if action == "history":
            now = datetime.utcnow()
            from_time = now - timedelta(hours=hours_back)
            entries = store.get_routine_range(from_time, now)
            return {
                "period": f"last {hours_back} hours",
                "entries": [
                    {
                        "time": e.timestamp.strftime("%I:%M %p"),
                        "activity": e.activity,
                        "location": e.location,
                    }
                    for e in entries
                ],
            }

        # Default: today
        entries = store.get_routine_today()
        return {
            "date": datetime.utcnow().date().isoformat(),
            "entries": [
                {
                    "time": e.timestamp.strftime("%I:%M %p"),
                    "activity": e.activity,
                    "location": e.location,
                }
                for e in entries
            ],
        }
    finally:
        store.close()
