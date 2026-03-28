# Alzheimer's Caregiver Assistant — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a backend agent orchestration system that ingests live video frames, observes the patient's environment via Claude vision, and assists with reminders, item tracking, and emergency response through a LangGraph agent.

**Architecture:** Single-process async FastAPI app. Websocket receives JPEG frames, buffers them in 5-second windows, dispatches async observer jobs (raw Anthropic SDK vision calls). Observations feed into a shared in-memory context. A LangGraph ReAct agent reads that context and has four tool skills. User interacts via POST `/speech`.

**Tech Stack:** Python, FastAPI, uvicorn, anthropic SDK, langgraph, langchain-anthropic, langchain-core, twilio, pydantic

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `src/__init__.py`
- Create: `src/observer/__init__.py`
- Create: `src/agent/__init__.py`
- Create: `src/skills/__init__.py`
- Create: `src/logging/__init__.py`
- Create: `data/calendar.json`
- Create: `data/.gitkeep`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create `pyproject.toml`**

```toml
[project]
name = "multimodal-frontier-project"
version = "0.1.0"
description = "Alzheimer's caregiver assistant — backend agent orchestration"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "websockets>=13.0",
    "anthropic>=0.40.0",
    "langgraph>=0.2.0",
    "langchain-anthropic>=0.3.0",
    "langchain-core>=0.3.0",
    "twilio>=9.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Create `.env.example`**

```
ANTHROPIC_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
EMERGENCY_CONTACT_NUMBER=
FRAME_SAMPLE_RATE=2
OBSERVER_WINDOW_SECONDS=5
```

**Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.env
data/agent_log.jsonl
.venv/
*.egg-info/
dist/
build/
```

**Step 4: Create all `__init__.py` files**

All empty files:
- `src/__init__.py`
- `src/observer/__init__.py`
- `src/agent/__init__.py`
- `src/skills/__init__.py`
- `src/logging/__init__.py`
- `tests/__init__.py`

**Step 5: Create `data/calendar.json`**

```json
{"events": []}
```

**Step 6: Create `tests/conftest.py`**

```python
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
```

**Step 7: Install dependencies**

Run: `pip install -e ".[dev]"`

**Step 8: Commit**

```bash
git add pyproject.toml .env.example .gitignore src/ data/ tests/
git commit -m "feat: project scaffolding with dependencies and directory structure"
```

---

### Task 2: Pydantic Models & Config

**Files:**
- Create: `src/models.py`
- Create: `src/config.py`
- Create: `tests/test_models.py`

**Step 1: Write tests for models**

```python
# tests/test_models.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `src.models` does not exist yet

**Step 3: Write `src/models.py`**

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ObjectSighting(BaseModel):
    name: str
    location: str


class Observation(BaseModel):
    timestamp: str
    actions: list[str] = Field(default_factory=list)
    objects: list[ObjectSighting] = Field(default_factory=list)
    safety_concerns: list[str] = Field(default_factory=list)
    urgency: Literal["none", "low", "high", "emergency"] = "none"

    @property
    def is_urgent(self) -> bool:
        return self.urgency in ("high", "emergency")


class CalendarEvent(BaseModel):
    id: str
    title: str
    datetime: str
    description: str = ""
    reminder_minutes_before: int = 15


class AgentLogEntry(BaseModel):
    timestamp: str
    trigger: Literal["speech", "proactive"]
    input: str
    tool_calls: list[dict] = Field(default_factory=list)
    response: str
```

**Step 4: Write `src/config.py`**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    emergency_contact_number: str = ""
    frame_sample_rate: int = 2
    observer_window_seconds: int = 5

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/models.py src/config.py tests/test_models.py
git commit -m "feat: pydantic models for observations, calendar events, and config"
```

---

### Task 3: Shared In-Memory Context

**Files:**
- Create: `src/agent/context.py`
- Create: `tests/test_context.py`

**Step 1: Write tests for shared context**

```python
# tests/test_context.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_context.py -v`
Expected: FAIL — `src.agent.context` does not exist yet

**Step 3: Write `src/agent/context.py`**

```python
import asyncio
from collections import deque

from src.models import Observation


class SharedContext:
    def __init__(self, max_observations: int = 100):
        self._observations: deque[Observation] = deque(maxlen=max_observations)
        self._last_seen: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    @property
    def recent_observations(self) -> list[Observation]:
        return list(self._observations)

    @property
    def last_seen(self) -> dict[str, dict]:
        return dict(self._last_seen)

    def add_observation(self, observation: Observation) -> None:
        self._observations.append(observation)
        for obj in observation.objects:
            self._last_seen[obj.name] = {
                "location": obj.location,
                "timestamp": observation.timestamp,
            }

    async def add_observation_async(self, observation: Observation) -> None:
        async with self._lock:
            self.add_observation(observation)

    def get_summary(self) -> str:
        lines = []
        if self._last_seen:
            lines.append("## Last Seen Items")
            for name, info in self._last_seen.items():
                lines.append(f"- {name}: {info['location']} (at {info['timestamp']})")
        if self._observations:
            lines.append("\n## Recent Observations")
            for obs in list(self._observations)[-10:]:
                for action in obs.actions:
                    lines.append(f"- [{obs.timestamp}] {action}")
                for concern in obs.safety_concerns:
                    lines.append(f"- [{obs.timestamp}] SAFETY: {concern}")
        return "\n".join(lines) if lines else "No observations yet."
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_context.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/agent/context.py tests/test_context.py
git commit -m "feat: shared in-memory context with observation tracking and last-seen dict"
```

---

### Task 4: JSONL Logger

**Files:**
- Create: `src/logging/logger.py`
- Create: `tests/test_logger.py`

**Step 1: Write tests for logger**

```python
# tests/test_logger.py
import json
import tempfile
from pathlib import Path

from src.logging.logger import AgentLogger


def test_log_entry_appends_to_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        log_path = f.name

    logger = AgentLogger(log_path)
    logger.log(
        trigger="speech",
        input_text="where are my keys?",
        tool_calls=[],
        response="Your keys were last seen on the kitchen counter.",
    )

    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["trigger"] == "speech"
    assert entry["input"] == "where are my keys?"
    assert "timestamp" in entry

    Path(log_path).unlink()


def test_log_multiple_entries():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        log_path = f.name

    logger = AgentLogger(log_path)
    logger.log(trigger="speech", input_text="hello", tool_calls=[], response="hi")
    logger.log(trigger="proactive", input_text="fall detected", tool_calls=[], response="calling emergency")

    with open(log_path) as f:
        lines = f.readlines()
    assert len(lines) == 2

    Path(log_path).unlink()
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_logger.py -v`
Expected: FAIL

**Step 3: Write `src/logging/logger.py`**

```python
import json
from datetime import datetime, timezone
from pathlib import Path


class AgentLogger:
    def __init__(self, log_path: str = "data/agent_log.jsonl"):
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        trigger: str,
        input_text: str,
        tool_calls: list[dict],
        response: str,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trigger": trigger,
            "input": input_text,
            "tool_calls": tool_calls,
            "response": response,
        }
        with open(self._log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_logger.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/logging/logger.py tests/test_logger.py
git commit -m "feat: append-only JSONL agent logger"
```

---

### Task 5: Frame Buffer

**Files:**
- Create: `src/observer/buffer.py`
- Create: `tests/test_buffer.py`

**Step 1: Write tests for frame buffer**

```python
# tests/test_buffer.py
import time
from src.observer.buffer import FrameBuffer


def test_add_frame():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    buf.add_frame(b"fake-jpeg-data")
    assert len(buf._frames) == 1


def test_snapshot_returns_frames():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    for i in range(5):
        buf.add_frame(f"frame-{i}".encode())
    snapshot = buf.snapshot()
    assert len(snapshot) == 5
    assert all(isinstance(ts, str) and isinstance(data, bytes) for ts, data in snapshot)


def test_snapshot_clears_buffer():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    for i in range(5):
        buf.add_frame(f"frame-{i}".encode())
    buf.snapshot()
    assert len(buf._frames) == 0


def test_should_dispatch_false_when_empty():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    assert not buf.should_dispatch()


def test_expected_frame_count():
    buf = FrameBuffer(window_seconds=5, sample_rate=2)
    assert buf.expected_frame_count == 10
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_buffer.py -v`
Expected: FAIL

**Step 3: Write `src/observer/buffer.py`**

```python
from collections import deque
from datetime import datetime, timezone


class FrameBuffer:
    def __init__(self, window_seconds: int = 5, sample_rate: int = 2):
        self._window_seconds = window_seconds
        self._sample_rate = sample_rate
        self._frames: deque[tuple[str, bytes]] = deque()
        self._window_start: float | None = None

    @property
    def expected_frame_count(self) -> int:
        return self._window_seconds * self._sample_rate

    def add_frame(self, frame_data: bytes) -> None:
        now = datetime.now(timezone.utc)
        if self._window_start is None:
            self._window_start = now.timestamp()
        self._frames.append((now.isoformat(), frame_data))

    def should_dispatch(self) -> bool:
        if not self._frames or self._window_start is None:
            return False
        elapsed = datetime.now(timezone.utc).timestamp() - self._window_start
        return elapsed >= self._window_seconds

    def snapshot(self) -> list[tuple[str, bytes]]:
        frames = list(self._frames)
        self._frames.clear()
        self._window_start = None
        return frames
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_buffer.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/observer/buffer.py tests/test_buffer.py
git commit -m "feat: frame buffer with 5-second windowing and snapshot dispatch"
```

---

### Task 6: Observer (Claude Vision Calls)

**Files:**
- Create: `src/observer/observer.py`
- Create: `src/agent/prompts.py`

**Step 1: Write `src/agent/prompts.py`**

```python
OBSERVER_SYSTEM_PROMPT = """\
You are a home monitoring assistant observing a live camera feed for an \
Alzheimer's patient. Analyze the provided frames and respond with ONLY a \
JSON object (no markdown, no extra text) in this exact schema:

{
  "timestamp": "<current ISO 8601 timestamp>",
  "actions": ["<description of actions observed>"],
  "objects": [{"name": "<object>", "location": "<where in the scene>"}],
  "safety_concerns": ["<any concerns, or empty list>"],
  "urgency": "none|low|high|emergency"
}

Urgency levels:
- none: normal activity
- low: mildly concerning but not dangerous
- high: needs attention soon (e.g., left stove on, wandering near door)
- emergency: immediate danger (e.g., fall, fire, medical distress)
"""

AGENT_SYSTEM_PROMPT = """\
You are a compassionate caregiver assistant for an Alzheimer's patient. \
You have access to a live observation feed from cameras in the patient's home, \
a calendar system, and an emergency calling system.

Your responsibilities:
1. Answer the patient's questions warmly and simply
2. Help them find lost items using observation data
3. Manage their calendar and reminders
4. Call emergency contacts when there is genuine danger

Always be patient, clear, and reassuring. Use short, simple sentences.

## Current Context
{context_summary}
"""
```

**Step 2: Write `src/observer/observer.py`**

```python
import base64
import json
import logging

import anthropic

from src.agent.prompts import OBSERVER_SYSTEM_PROMPT
from src.models import Observation

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic()
    return _client


async def observe_frames(frames: list[tuple[str, bytes]]) -> Observation:
    """Send a window of JPEG frames to Claude vision and return an Observation."""
    client = get_client()

    content_blocks: list[dict] = []
    for _timestamp, jpeg_bytes in frames:
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": base64.standard_b64encode(jpeg_bytes).decode("utf-8"),
            },
        })

    content_blocks.append({
        "type": "text",
        "text": (
            f"These are {len(frames)} sequential frames from a home camera, "
            f"spanning from {frames[0][0]} to {frames[-1][0]}. "
            "Analyze the scene and respond with the JSON observation."
        ),
    })

    response = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=OBSERVER_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content_blocks}],
    )

    response_text = response.content[0].text

    try:
        data = json.loads(response_text)
        return Observation(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.error(f"Failed to parse observer response: {e}\nRaw: {response_text}")
        return Observation(
            timestamp=frames[-1][0],
            actions=["[parse error] " + response_text[:200]],
            objects=[],
            safety_concerns=[],
            urgency="none",
        )
```

**Step 3: Commit**

```bash
git add src/observer/observer.py src/agent/prompts.py
git commit -m "feat: observer with Claude vision API and system prompts"
```

---

### Task 7: Calendar Skills

**Files:**
- Create: `src/skills/calendar_read.py`
- Create: `src/skills/calendar_write.py`
- Create: `tests/test_calendar_skills.py`

**Step 1: Write tests for calendar skills**

```python
# tests/test_calendar_skills.py
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
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_calendar_skills.py -v`
Expected: FAIL

**Step 3: Write `src/skills/calendar_read.py`**

```python
import json
from pathlib import Path

from langchain_core.tools import tool

CALENDAR_PATH = "data/calendar.json"


def read_calendar_file(path: str = CALENDAR_PATH) -> list[dict]:
    """Read all events from the calendar file."""
    cal_path = Path(path)
    if not cal_path.exists():
        return []
    with open(cal_path) as f:
        data = json.load(f)
    return data.get("events", [])


@tool
def calendar_read(date_filter: str = "") -> str:
    """Read upcoming events from the calendar. Optionally filter by date prefix (e.g. '2026-03-29')."""
    events = read_calendar_file()
    if date_filter:
        events = [e for e in events if e["datetime"].startswith(date_filter)]
    if not events:
        return "No upcoming events found."
    lines = []
    for e in events:
        lines.append(f"- {e['title']} at {e['datetime']}: {e['description']}")
    return "\n".join(lines)
```

**Step 4: Write `src/skills/calendar_write.py`**

```python
import json
import uuid
from pathlib import Path

from langchain_core.tools import tool

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


@tool
def calendar_write(title: str, datetime_str: str, description: str = "", reminder_minutes_before: int = 15) -> str:
    """Add a new event to the calendar. Provide a title, datetime (ISO format), optional description, and reminder time in minutes."""
    event = {
        "id": f"evt-{uuid.uuid4().hex[:8]}",
        "title": title,
        "datetime": datetime_str,
        "description": description,
        "reminder_minutes_before": reminder_minutes_before,
    }
    write_calendar_file(event=event)
    return f"Event '{title}' added for {datetime_str}."
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_calendar_skills.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add src/skills/calendar_read.py src/skills/calendar_write.py tests/test_calendar_skills.py
git commit -m "feat: calendar read and write skills with file-based persistence"
```

---

### Task 8: AnswerQuestion Skill

**Files:**
- Create: `src/skills/answer_question.py`

**Step 1: Write `src/skills/answer_question.py`**

```python
from langchain_core.tools import tool

from src.agent.context import SharedContext

# This will be set at app startup to the shared context instance
_shared_context: SharedContext | None = None


def set_shared_context(ctx: SharedContext) -> None:
    global _shared_context
    _shared_context = ctx


@tool
def answer_question(question: str) -> str:
    """Look up information from recent observations and last-seen items to answer a question about the patient's environment, activities, or item locations."""
    if _shared_context is None:
        return "No observation context available."
    summary = _shared_context.get_summary()
    return f"Here is the current context to help answer '{question}':\n\n{summary}"
```

**Step 2: Commit**

```bash
git add src/skills/answer_question.py
git commit -m "feat: answer question skill backed by shared context"
```

---

### Task 9: CallEmergency Skill

**Files:**
- Create: `src/skills/call_emergency.py`

**Step 1: Write `src/skills/call_emergency.py`**

```python
import logging

from langchain_core.tools import tool
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from src.config import settings

logger = logging.getLogger(__name__)


def make_emergency_call(reason: str) -> str:
    """Place an emergency call via Twilio."""
    if not settings.twilio_account_sid or not settings.emergency_contact_number:
        logger.warning("Twilio not configured — skipping emergency call")
        return "Emergency call skipped: Twilio not configured."

    client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    twiml = VoiceResponse()
    twiml.say(
        f"This is an automated alert from the caregiver assistant. {reason}. "
        "Please check on the patient immediately.",
        voice="alice",
    )

    call = client.calls.create(
        twiml=str(twiml),
        to=settings.emergency_contact_number,
        from_=settings.twilio_from_number,
    )

    logger.info(f"Emergency call initiated: SID={call.sid}, reason={reason}")
    return f"Emergency call placed (SID: {call.sid}). Reason: {reason}"


@tool
def call_emergency(reason: str) -> str:
    """Call the emergency contact via phone. Only use this for genuine emergencies such as falls, fires, or medical distress. Provide a clear reason for the call."""
    return make_emergency_call(reason)
```

**Step 2: Commit**

```bash
git add src/skills/call_emergency.py
git commit -m "feat: emergency call skill via Twilio with TTS alert"
```

---

### Task 10: LangGraph Main Agent

**Files:**
- Create: `src/agent/graph.py`

**Step 1: Write `src/agent/graph.py`**

```python
import logging

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agent.context import SharedContext
from src.agent.prompts import AGENT_SYSTEM_PROMPT
from src.logging.logger import AgentLogger
from src.skills.answer_question import answer_question, set_shared_context
from src.skills.calendar_read import calendar_read
from src.skills.calendar_write import calendar_write
from src.skills.call_emergency import call_emergency

logger = logging.getLogger(__name__)


class MainAgent:
    def __init__(self, shared_context: SharedContext, agent_logger: AgentLogger):
        self._context = shared_context
        self._logger = agent_logger

        set_shared_context(shared_context)

        model = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            temperature=0,
        )

        self._tools = [calendar_read, calendar_write, answer_question, call_emergency]

        self._agent = create_react_agent(
            model=model,
            tools=self._tools,
        )

    def _build_system_message(self) -> str:
        return AGENT_SYSTEM_PROMPT.format(
            context_summary=self._context.get_summary()
        )

    async def handle_speech(self, text: str) -> str:
        """Handle a user speech input and return the agent response."""
        system_msg = self._build_system_message()

        response = await self._agent.ainvoke({
            "messages": [
                {"role": "system", "content": system_msg},
                HumanMessage(content=text),
            ]
        })

        # Extract the final assistant message
        ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
        result = ai_messages[-1].content if ai_messages else "I'm sorry, I couldn't process that."

        # Extract tool calls for logging
        tool_calls = []
        for m in response["messages"]:
            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({"name": tc["name"], "args": tc["args"]})

        self._logger.log(
            trigger="speech",
            input_text=text,
            tool_calls=tool_calls,
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)

    async def handle_proactive(self, observation_summary: str) -> str:
        """Handle a proactive trigger from an urgent observation."""
        system_msg = self._build_system_message()

        prompt = (
            f"URGENT OBSERVATION: {observation_summary}\n\n"
            "Assess this situation and take appropriate action. "
            "If this is a genuine emergency, call the emergency contact."
        )

        response = await self._agent.ainvoke({
            "messages": [
                {"role": "system", "content": system_msg},
                HumanMessage(content=prompt),
            ]
        })

        ai_messages = [m for m in response["messages"] if m.type == "ai" and m.content]
        result = ai_messages[-1].content if ai_messages else ""

        tool_calls = []
        for m in response["messages"]:
            if m.type == "ai" and hasattr(m, "tool_calls") and m.tool_calls:
                for tc in m.tool_calls:
                    tool_calls.append({"name": tc["name"], "args": tc["args"]})

        self._logger.log(
            trigger="proactive",
            input_text=observation_summary,
            tool_calls=tool_calls,
            response=result if isinstance(result, str) else str(result),
        )

        return result if isinstance(result, str) else str(result)
```

**Step 2: Commit**

```bash
git add src/agent/graph.py
git commit -m "feat: LangGraph ReAct main agent with speech and proactive triggers"
```

---

### Task 11: FastAPI Server

**Files:**
- Create: `src/server.py`

**Step 1: Write `src/server.py`**

```python
import asyncio
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.agent.context import SharedContext
from src.agent.graph import MainAgent
from src.config import settings
from src.logging.logger import AgentLogger
from src.observer.buffer import FrameBuffer
from src.observer.observer import observe_frames

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Alzheimer's Caregiver Assistant")

# Shared state — initialized on startup
shared_context = SharedContext(max_observations=100)
agent_logger = AgentLogger("data/agent_log.jsonl")
main_agent = MainAgent(shared_context=shared_context, agent_logger=agent_logger)
frame_buffer = FrameBuffer(
    window_seconds=settings.observer_window_seconds,
    sample_rate=settings.frame_sample_rate,
)


class SpeechRequest(BaseModel):
    text: str


class SpeechResponse(BaseModel):
    response: str


async def process_observer_window(frames: list[tuple[str, bytes]]) -> None:
    """Run an observer job on a window of frames and update shared context."""
    try:
        observation = await observe_frames(frames)
        await shared_context.add_observation_async(observation)
        logger.info(f"Observation: {observation.actions}, urgency={observation.urgency}")

        if observation.is_urgent:
            summary = "; ".join(observation.safety_concerns or observation.actions)
            logger.warning(f"Urgent observation detected: {summary}")
            asyncio.create_task(main_agent.handle_proactive(summary))

    except Exception as e:
        logger.error(f"Observer job failed: {e}")


async def dispatch_loop() -> None:
    """Background loop that checks the buffer and dispatches observer jobs."""
    while True:
        if frame_buffer.should_dispatch():
            frames = frame_buffer.snapshot()
            if frames:
                asyncio.create_task(process_observer_window(frames))
        await asyncio.sleep(0.5)


@app.on_event("startup")
async def startup():
    asyncio.create_task(dispatch_loop())
    logger.info("Caregiver assistant started")


@app.websocket("/video/stream")
async def video_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("Video stream connected")
    try:
        while True:
            data = await websocket.receive_bytes()
            frame_buffer.add_frame(data)
    except WebSocketDisconnect:
        logger.info("Video stream disconnected")


@app.post("/speech", response_model=SpeechResponse)
async def speech(request: SpeechRequest):
    response_text = await main_agent.handle_speech(request.text)
    return SpeechResponse(response=response_text)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "observations": len(shared_context.recent_observations),
        "items_tracked": len(shared_context.last_seen),
    }
```

**Step 2: Verify server can import without errors**

Run: `python -c "from src.server import app; print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add src/server.py
git commit -m "feat: FastAPI server with websocket video ingestion, /speech endpoint, and observer dispatch loop"
```

---

### Task 12: Integration Smoke Test

**Files:**
- Create: `tests/test_server.py`

**Step 1: Write integration test**

```python
# tests/test_server.py
import pytest
from httpx import AsyncClient, ASGITransport

from src.server import app


@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "observations" in data
    assert "items_tracked" in data
```

**Step 2: Run test**

Run: `pytest tests/test_server.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/test_server.py
git commit -m "feat: integration smoke test for health endpoint"
```

---

### Task 13: Final Verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

**Step 2: Verify server starts**

Run: `timeout 5 python -m uvicorn src.server:app --host 0.0.0.0 --port 8000 || true`
Expected: Server starts without errors (will exit after 5s timeout)

**Step 3: Final commit with any remaining files**

```bash
git add -A
git status
# If any unstaged files remain, commit them
```
