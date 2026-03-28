import pytest
from src.agent.context import SharedContext
from src.models import Observation


@pytest.fixture
def ctx():
    return SharedContext(max_observations=5)


def test_add_observation(ctx, sample_observation):
    obs = Observation(**sample_observation)
    ctx.add_observation(obs)
    assert len(ctx.recent_observations) == 1
    assert ctx.recent_observations[0].actions[0] == "user placed keys on kitchen counter"


def test_observations_capped(ctx):
    for i in range(10):
        obs = Observation(
            timestamp=f"2026-03-28T14:{i:02d}:00",
            actions=[f"action {i}"],
            objects=[],
            safety_concerns=[],
            urgency="none",
        )
        ctx.add_observation(obs)
    assert len(ctx.recent_observations) == 5


def test_last_seen_updated(ctx, sample_observation):
    obs = Observation(**sample_observation)
    ctx.add_observation(obs)
    assert "keys" in ctx.last_seen
    assert ctx.last_seen["keys"]["location"] == "kitchen counter"


def test_last_seen_updates_on_new_sighting(ctx):
    obs1 = Observation(
        timestamp="2026-03-28T14:00:00",
        actions=[],
        objects=[{"name": "keys", "location": "kitchen counter"}],
        safety_concerns=[],
        urgency="none",
    )
    obs2 = Observation(
        timestamp="2026-03-28T14:05:00",
        actions=[],
        objects=[{"name": "keys", "location": "living room table"}],
        safety_concerns=[],
        urgency="none",
    )
    ctx.add_observation(obs1)
    ctx.add_observation(obs2)
    assert ctx.last_seen["keys"]["location"] == "living room table"
    assert ctx.last_seen["keys"]["timestamp"] == "2026-03-28T14:05:00"


def test_get_context_summary(ctx, sample_observation):
    obs = Observation(**sample_observation)
    ctx.add_observation(obs)
    summary = ctx.get_summary()
    assert "keys" in summary
    assert "kitchen counter" in summary
