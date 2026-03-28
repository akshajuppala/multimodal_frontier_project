"""
Medication tool — track medication schedules and check compliance.

Proactively used by the agent around scheduled medication times,
and reactively when the user asks about their meds.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from langchain_core.tools import tool

from server.state.store import StateStore


@tool
def medication_check(action: str = "status", medication_name: Optional[str] = None, scheduled_time: Optional[str] = None) -> dict:
    """Check medication schedule or log that a medication was taken.

    Args:
        action: One of "status" (check what's due), "taken" (mark as taken), or "list" (show all meds).
        medication_name: Required when action is "taken". Name of the medication taken.
        scheduled_time: Required when action is "taken". The scheduled time slot (e.g., "08:00").

    Returns:
        Medication status, schedule, or confirmation of logging.
    """
    store = StateStore()
    try:
        if action == "list":
            meds = store.get_medications()
            return {
                "medications": [
                    {
                        "name": m.name,
                        "dosage": m.dosage,
                        "times": m.scheduled_times,
                        "notes": m.notes,
                    }
                    for m in meds
                ]
            }

        if action == "taken":
            if not medication_name or not scheduled_time:
                return {"error": "medication_name and scheduled_time are required for 'taken' action"}
            store.log_medication_taken(medication_name, scheduled_time)
            return {
                "logged": True,
                "medication": medication_name,
                "time": scheduled_time,
                "taken_at": datetime.utcnow().isoformat(),
            }

        # Default: status check
        status = store.get_medication_status_today()
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")

        overdue = []
        upcoming = []
        taken = []

        for entry in status:
            if entry["taken"]:
                taken.append(entry)
            elif entry["scheduled_time"] <= current_time:
                overdue.append(entry)
            else:
                upcoming.append(entry)

        return {
            "current_time": current_time,
            "overdue": overdue,
            "upcoming": upcoming,
            "taken_today": taken,
        }
    finally:
        store.close()
