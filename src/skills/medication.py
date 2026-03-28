"""Medication tracking skill — schedule checks and compliance logging."""
from __future__ import annotations

from datetime import datetime, timezone

import railtracks as rt

from src.state.store import get_store


@rt.function_node
def medication_check(action: str = "status", medication_name: str = "", scheduled_time: str = "") -> str:
    """Check medication schedule or log that a medication was taken.

    Actions: "status" (what's due/overdue), "taken" (mark as taken), "list" (all meds).

    Args:
        action (str): One of "status", "taken", or "list".
        medication_name (str): Required when action is "taken". Name of the medication.
        scheduled_time (str): Required when action is "taken". The scheduled time slot (e.g. "08:00").
    """
    store = get_store()

    if action == "list":
        meds = store.get_medications()
        if not meds:
            return "No medications registered yet."
        lines = []
        for m in meds:
            times = ", ".join(m["scheduled_times"])
            lines.append(f"- {m['name']} ({m['dosage']}) at {times}")
        return "Medications:\n" + "\n".join(lines)

    if action == "taken":
        if not medication_name or not scheduled_time:
            return "Please provide medication_name and scheduled_time to log."
        store.log_medication_taken(medication_name, scheduled_time)
        return f"Logged: {medication_name} taken for the {scheduled_time} dose."

    # Default: status
    status = store.get_medication_status_today()
    if not status:
        return "No medications registered yet."

    now = datetime.now(timezone.utc)
    current_time = now.strftime("%H:%M")

    overdue, upcoming, taken = [], [], []
    for entry in status:
        label = f"{entry['medication']} ({entry['dosage']}) — {entry['scheduled_time']}"
        if entry["taken"]:
            taken.append(f"  ✓ {label} (taken at {entry['taken_at'][:16]})")
        elif entry["scheduled_time"] <= current_time:
            overdue.append(f"  ⚠ {label} — OVERDUE")
        else:
            upcoming.append(f"  ○ {label}")

    parts = []
    if overdue:
        parts.append("Overdue:\n" + "\n".join(overdue))
    if upcoming:
        parts.append("Upcoming:\n" + "\n".join(upcoming))
    if taken:
        parts.append("Taken today:\n" + "\n".join(taken))
    return "\n\n".join(parts) if parts else "All medications accounted for today."
