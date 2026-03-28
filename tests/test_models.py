from src.models import Observation, ObjectSighting, CalendarEvent, AgentLogEntry


def test_observation_from_dict(sample_observation):
    obs = Observation(**sample_observation)
    assert obs.urgency == "none"
    assert len(obs.objects) == 1
    assert obs.objects[0].name == "keys"


def test_observation_is_urgent():
    obs = Observation(
        timestamp="2026-03-28T14:02:00",
        actions=["user fell down"],
        objects=[],
        safety_concerns=["fall detected"],
        urgency="emergency",
    )
    assert obs.is_urgent


def test_observation_not_urgent():
    obs = Observation(
        timestamp="2026-03-28T14:02:00",
        actions=["user sitting"],
        objects=[],
        safety_concerns=[],
        urgency="none",
    )
    assert not obs.is_urgent


def test_calendar_event_from_dict(sample_calendar_event):
    event = CalendarEvent(**sample_calendar_event)
    assert event.title == "Doctor appointment"
    assert event.reminder_minutes_before == 30


def test_agent_log_entry():
    entry = AgentLogEntry(
        timestamp="2026-03-28T14:02:00",
        trigger="speech",
        input="where are my keys?",
        tool_calls=[],
        response="Your keys were last seen on the kitchen counter.",
    )
    assert entry.trigger == "speech"
