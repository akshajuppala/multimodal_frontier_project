"""
Calendar tools — read and write calendar events.

Uses Google Calendar API when credentials are available,
falls back to local SQLite store for hackathon/dev usage.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from langchain_core.tools import tool

from server.state.store import StateStore

# Google Calendar imports — optional, gracefully degrade
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    HAS_GOOGLE = True
except ImportError:
    HAS_GOOGLE = False

GOOGLE_CREDS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "primary")


def _get_google_service():
    if not HAS_GOOGLE or not GOOGLE_CREDS_PATH:
        return None
    try:
        creds = Credentials.from_authorized_user_file(GOOGLE_CREDS_PATH)
        return build("calendar", "v3", credentials=creds)
    except Exception:
        return None


@tool
def calendar_read(date: Optional[str] = None) -> dict:
    """Read calendar events for a given date.

    Args:
        date: Date string in YYYY-MM-DD format. Defaults to today.

    Returns:
        Dictionary with list of events for the day.
    """
    target_date = date or datetime.utcnow().date().isoformat()

    # Try Google Calendar first
    service = _get_google_service()
    if service:
        try:
            time_min = f"{target_date}T00:00:00Z"
            time_max = f"{target_date}T23:59:59Z"
            result = (
                service.events()
                .list(
                    calendarId=GOOGLE_CALENDAR_ID,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            events = []
            for item in result.get("items", []):
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                events.append({
                    "id": item["id"],
                    "title": item.get("summary", "Untitled"),
                    "time": start,
                    "location": item.get("location", ""),
                    "notes": item.get("description", ""),
                })
            return {"date": target_date, "events": events, "source": "google_calendar"}
        except Exception:
            pass

    # Fallback: local store
    store = StateStore()
    try:
        events = store.get_calendar_events(target_date)
        return {"date": target_date, "events": events, "source": "local"}
    finally:
        store.close()


@tool
def calendar_write(title: str, time: str, location: Optional[str] = None, notes: Optional[str] = None) -> dict:
    """Create a new calendar event.

    Args:
        title: Event title (e.g., "Doctor appointment with Dr. Smith").
        time: Event time in ISO format (e.g., "2024-03-28T14:00:00").
        location: Optional event location.
        notes: Optional notes about the event.

    Returns:
        Confirmation with the created event details.
    """
    event_id = str(uuid.uuid4())[:8]

    # Try Google Calendar
    service = _get_google_service()
    if service:
        try:
            event_time = datetime.fromisoformat(time)
            end_time = event_time + timedelta(hours=1)
            body = {
                "summary": title,
                "start": {"dateTime": event_time.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_time.isoformat(), "timeZone": "UTC"},
            }
            if location:
                body["location"] = location
            if notes:
                body["description"] = notes
            created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=body).execute()
            return {
                "success": True,
                "event_id": created["id"],
                "title": title,
                "time": time,
                "source": "google_calendar",
            }
        except Exception:
            pass

    # Fallback: local store
    store = StateStore()
    try:
        event = {"id": event_id, "title": title, "time": time, "location": location, "notes": notes}
        store.save_calendar_event(event)
        return {"success": True, "event_id": event_id, "title": title, "time": time, "source": "local"}
    finally:
        store.close()
