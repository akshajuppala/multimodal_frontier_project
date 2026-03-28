# Multimodal Frontier Project

An Alzheimer's caregiver assistant — a backend agent orchestration system that ingests live video frames via websocket, observes the patient's environment, and proactively assists with reminders, item tracking, and emergency response.

## Architecture

Single-process async Python application (FastAPI + uvicorn). Everything runs in one process — observer jobs are I/O-bound (Claude API calls) so async handles concurrency without blocking.

```
WS /video/stream              POST /speech
      │                             │
      ▼                             ▼
 Frame Buffer               Main Agent (LangGraph)
 (5-sec windows)            ┌─────────────────────┐
      │                     │ Skills:              │
      ▼                     │  - CalendarRead      │
 Observer Jobs              │  - CalendarWrite     │
 (async, raw Claude)        │  - AnswerQuestion    │
      │                     │  - CallEmergency     │
      │  writes to          └──────────┬──────────┘
      ▼  shared context                │
 In-Memory Context ◀──reads────────────┘
      │                                │
      ▼                                ▼
 agent_log.jsonl               TTS response out
```

## Core Components

### Observer Pipeline

- **Websocket endpoint** (`/video/stream`): Accepts JPEG frames from a camera source.
- **Frame buffer** (`src/observer/buffer.py`): Rolling deque of `(timestamp, frame_bytes)` tuples. Samples at ~2 frames/sec. Every 5 seconds, snapshots the window (~10 frames) and dispatches an async observer job.
- **Observer job** (`src/observer/observer.py`): Raw Anthropic SDK call — sends frames to Claude's vision API with a structured prompt. Returns a JSON observation:
  ```json
  {
    "timestamp": "2026-03-28T14:02:00",
    "actions": ["user placed keys on kitchen counter"],
    "objects": [{"name": "keys", "location": "kitchen counter"}],
    "safety_concerns": [],
    "urgency": "none"
  }
  ```
  Urgency levels: `none`, `low`, `high`, `emergency`. High/emergency triggers the main agent proactively.

### Shared Context (`src/agent/context.py`)

In-memory, thread-safe state:
- **Recent observations**: Capped list of last 100 observations.
- **Last seen dict**: `{"keys": {"location": "kitchen counter", "timestamp": "..."}}` — updated on every observation mentioning objects.

### Main Agent (`src/agent/graph.py`)

LangGraph ReAct-style agent loop using Claude as the LLM.

**Two entry points:**
1. **User query**: POST `/speech` with `{"text": "..."}` — user's speech-to-text input routed through the agent.
2. **Proactive trigger**: Observer flags urgency `high` or `emergency`, agent invoked automatically.

**System prompt** gives the agent its role as a caregiver assistant with access to the shared context (recent observations, last_seen dict).

### Skills (LangGraph Tool Nodes)

#### CalendarRead (`src/skills/calendar_read.py`)
- Reads `data/calendar.json`, returns upcoming events.
- Supports filtering by date range.

#### CalendarWrite (`src/skills/calendar_write.py`)
- Appends/updates events in `data/calendar.json`.
- Event schema: `{"id", "title", "datetime", "description", "reminder_minutes_before"}`.

#### AnswerQuestion (`src/skills/answer_question.py`)
- Packages relevant context (last_seen entries, recent observations) for the agent to answer questions like "where are my keys?" or "what did I do this morning?".

#### CallEmergency (`src/skills/call_emergency.py`)
- Uses Twilio API to call the preconfigured emergency contact.
- Takes a `reason` parameter, plays TTS message to the contact.
- High-stakes — agent should have high confidence before invoking.

### Logging (`src/logging/logger.py`)

All agent invocations appended to `data/agent_log.jsonl` — one JSON object per line:
```json
{"timestamp": "...", "trigger": "speech|proactive", "input": "...", "tool_calls": [...], "response": "..."}
```

## Project Structure

```
multimodal_frontier_project/
├── CLAUDE.md
├── pyproject.toml
├── .env                          # API keys and config (not committed)
├── src/
│   ├── __init__.py
│   ├── server.py                 # FastAPI app, websocket + /speech endpoints
│   ├── observer/
│   │   ├── __init__.py
│   │   ├── buffer.py             # Frame buffer, 5-sec windowing
│   │   └── observer.py           # Raw Claude vision calls
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── graph.py              # LangGraph agent definition
│   │   ├── context.py            # Shared in-memory context
│   │   └── prompts.py            # System prompts
│   ├── skills/
│   │   ├── __init__.py
│   │   ├── calendar_read.py
│   │   ├── calendar_write.py
│   │   ├── answer_question.py
│   │   └── call_emergency.py
│   └── logging/
│       ├── __init__.py
│       └── logger.py
├── data/
│   ├── calendar.json
│   └── agent_log.jsonl
└── tests/
```

## Dependencies

- `fastapi` + `uvicorn` — async server
- `websockets` — frame ingestion
- `anthropic` — Claude vision API (observer)
- `langgraph` + `langchain-anthropic` — main agent orchestration
- `twilio` — emergency calls
- `pydantic` — data models

## Configuration (.env)

```
ANTHROPIC_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
EMERGENCY_CONTACT_NUMBER=
FRAME_SAMPLE_RATE=2          # frames per second to sample
OBSERVER_WINDOW_SECONDS=5    # seconds per observer job window
```

## Conventions

- All async code uses `asyncio` — no threads unless strictly necessary.
- Observer jobs are fire-and-forget via `asyncio.create_task()`.
- Shared context access must be thread-safe (use locks if needed).
- Skills are implemented as LangGraph tool functions decorated with `@tool`.
- Logging is append-only JSONL — never overwrite the log file.
- Calendar is a simple JSON file — read/write with file locks to avoid corruption.
