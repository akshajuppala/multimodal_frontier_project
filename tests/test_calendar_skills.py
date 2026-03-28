import json
import tempfile
from pathlib import Path

import pytest

from src.skills.calendar_read import read_calendar_file
from src.skills.calendar_write import write_calendar_file


@pytest.fixture
def temp_calendar():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"events": []}, f)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


@pytest.fixture
def populated_calendar():
    events = {
        "events": [
            {
                "id": "evt-001",
                "title": "Doctor appointment",
                "datetime": "2026-03-29T10:00:00",
                "description": "Annual checkup",
                "reminder_minutes_before": 30,
            },
            {
                "id": "evt-002",
                "title": "Lunch with Mary",
                "datetime": "2026-03-29T12:00:00",
                "description": "",
                "reminder_minutes_before": 15,
            },
        ]
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(events, f)
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)


def test_read_empty_calendar(temp_calendar):
    result = read_calendar_file(temp_calendar)
    assert result == []


def test_read_populated_calendar(populated_calendar):
    result = read_calendar_file(populated_calendar)
    assert len(result) == 2
    assert result[0]["title"] == "Doctor appointment"


def test_write_new_event(temp_calendar):
    event = {
        "id": "evt-100",
        "title": "Take medication",
        "datetime": "2026-03-28T18:00:00",
        "description": "Evening pills",
        "reminder_minutes_before": 10,
    }
    write_calendar_file(temp_calendar, event)
    result = read_calendar_file(temp_calendar)
    assert len(result) == 1
    assert result[0]["title"] == "Take medication"


def test_write_update_existing_event(populated_calendar):
    updated = {
        "id": "evt-001",
        "title": "Doctor appointment (rescheduled)",
        "datetime": "2026-03-30T10:00:00",
        "description": "Annual checkup",
        "reminder_minutes_before": 30,
    }
    write_calendar_file(populated_calendar, updated)
    result = read_calendar_file(populated_calendar)
    assert len(result) == 2
    match = [e for e in result if e["id"] == "evt-001"][0]
    assert match["title"] == "Doctor appointment (rescheduled)"
