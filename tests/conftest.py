import pytest


@pytest.fixture
def sample_calendar_event():
    return {
        "id": "evt-001",
        "title": "Doctor appointment",
        "datetime": "2026-03-29T10:00:00",
        "description": "Annual checkup with Dr. Smith",
        "reminder_minutes_before": 30,
    }


@pytest.fixture
def sample_observation():
    return {
        "timestamp": "2026-03-28T14:02:00",
        "actions": ["user placed keys on kitchen counter"],
        "objects": [{"name": "keys", "location": "kitchen counter"}],
        "safety_concerns": [],
        "urgency": "none",
    }
