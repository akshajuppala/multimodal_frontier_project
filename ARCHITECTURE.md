# Alzheimer's Caretaker App — Architecture

## High-Level Overview

**Single-agent design orchestrated by LangGraph.** One LLM with full context makes all decisions and calls tools — including a vision tool to analyze camera frames. No separate observer agent; the main agent decides when and whether to analyze incoming frames.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         iOS Swift App                                   │
│                                                                         │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────────────┐  │
│  │  Camera   │  │  STT (Speech │  │  Record /  │  │  Audio Playback  │  │
│  │  Feed     │  │  to Text)    │  │  Stop Btn  │  │  (TTS responses) │  │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └────────▲─────────┘  │
│       │               │                │                   │            │
│       │  Video Frames │  Raw Text      │                   │ TTS Audio  │
│       ▼               ▼                ▼                   │            │
│  ┌──────────────────────────────────────────────────────────┴────────┐  │
│  │                     WebSocket Client                              │  │
│  │  Sends: { type: "frame" | "question", payload: ... }             │  │
│  │  Receives: { type: "speech" | "alert", payload: ... }            │  │
│  └──────────────────────────┬───────────────────────────────────────┘  │
└─────────────────────────────┼───────────────────────────────────────────┘
                              │
                    WebSocket │ wss://
                              │
┌─────────────────────────────▼───────────────────────────────────────────┐
│                    Backend Server (Python / FastAPI)                     │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    WebSocket Router                                 │ │
│  │  frame    ──►  packaged as message → LangGraph Agent               │ │
│  │  question ──►  packaged as message → LangGraph Agent               │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                 LangGraph Agent (Single Agent Loop)                 │ │
│  │                                                                    │ │
│  │   ┌─────────┐    ┌─────────────────────────┐                      │ │
│  │   │  Agent   │───►│  Should I call a tool?  │                      │ │
│  │   │  (LLM)  │    │  Yes → tool node        │                      │ │
│  │   │         │◄───│  No  → END (wait)       │                      │ │
│  │   └─────────┘    └─────────────────────────┘                      │ │
│  │        │                                                           │ │
│  │        ▼ tool calls                                                │ │
│  │   ┌─────────────────────────────────────────────────────────────┐  │ │
│  │   │                    Tool Node                                 │  │ │
│  │   │                                                              │  │ │
│  │   │  analyze_frame ── Vision LLM call on camera frame            │  │ │
│  │   │  calendar_read ── Read events from calendar                  │  │ │
│  │   │  calendar_write── Create new calendar events                 │  │ │
│  │   │  answer_question─ Search state store for items/people        │  │ │
│  │   │  get_previous_state─ Historical observation lookup           │  │ │
│  │   │  speech_tool ──── TTS → audio pushed over WebSocket          │  │ │
│  │   │  medication_check─ Check/log medication compliance           │  │ │
│  │   │  daily_routine ── Log/query daily activities                 │  │ │
│  │   │  weather_check ── Current weather + practical advice         │  │ │
│  │   │  [call_emergency]─ Twilio emergency call (separate owner)    │  │ │
│  │   └─────────────────────────────────────────────────────────────┘  │ │
│  │        │                                                           │ │
│  │        │ results flow back to agent                                │ │
│  │        ▼                                                           │ │
│  │   Agent decides: call another tool? speak? stay quiet?             │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌─────────────────┐                                                    │
│  │  State Store     │  SQLite — observations, objects, people,          │
│  │  (SQLite)        │  medications, routine log, calendar events        │
│  └─────────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Agent Loop

```
         ┌──────────────────┐
         │   System Prompt   │  (prompts/main_agent_system.md)
         │   + Message Hist  │
         └────────┬─────────┘
                  │
                  ▼
         ┌──────────────────┐
         │    Agent Node     │  GPT-4o with tools bound
         │    (LLM call)     │
         └────────┬─────────┘
                  │
          ┌───────┴────────┐
          │  tool_calls?   │
          │                │
     Yes  ▼           No   ▼
  ┌──────────────┐    ┌─────┐
  │  Tool Node    │    │ END │
  │  (executes    │    └─────┘
  │   all calls)  │
  └──────┬───────┘
         │
         │ results appended to messages
         │
         └────────► back to Agent Node
```

---

## Data Flow

### Frame arrives from iOS app
1. WebSocket router receives `{ type: "frame", payload: { image: "base64..." } }`
2. Router packages it as a `HumanMessage` and invokes the LangGraph agent
3. Agent decides whether to call `analyze_frame` (based on time elapsed, visible changes)
4. If `analyze_frame` is called → vision LLM analyzes the frame → returns structured observation
5. Agent receives observation → decides: speak? remind? log routine? stay quiet?
6. If speaking → calls `speech_tool` → TTS audio sent back over WebSocket

### User asks a question
1. WebSocket router receives `{ type: "question", payload: { text: "Where are my keys?" } }`
2. Router packages as `HumanMessage` and invokes the agent
3. Agent calls `answer_question` → searches state store → finds object location
4. Agent calls `speech_tool` → speaks the answer to the user

---

## Tools

### analyze_frame
```
analyze_frame(frame_base64: str) -> dict

Sends the camera frame to a vision-capable LLM (GPT-4o) along with
the observer system prompt and previous state context. Returns
structured JSON observation (objects, people, activity, danger).
Automatically persists changes to the state store.
```

### calendar_read
```
calendar_read(date?: str) -> dict

Returns calendar events for the given date (YYYY-MM-DD).
Tries Google Calendar API first, falls back to local SQLite.
Defaults to today.
```

### calendar_write
```
calendar_write(title: str, time: str, location?: str, notes?: str) -> dict

Creates a calendar event. Tries Google Calendar, falls back to local.
```

### answer_question
```
answer_question(question: str) -> dict

Extracts keywords from the question and searches the state store for
matching objects, people, and observations. Returns structured results
with timestamps.
```

### get_previous_state
```
get_previous_state(hours_back: float = 4.0) -> dict

Retrieves historical observations and routine entries from the past
N hours. For "What did I do today?" type questions.
```

### speech_tool
```
speech_tool(text: str) -> dict

Converts text to speech (OpenAI TTS or ElevenLabs) and pushes audio
back over WebSocket to the iOS app. This is the only way the agent
communicates with the user.
```

### medication_check
```
medication_check(action: str, medication_name?: str, scheduled_time?: str) -> dict

Actions: "status" (what's due/overdue), "taken" (mark as taken), "list" (all meds).
Used proactively around scheduled times and reactively when user asks.
```

### daily_routine
```
daily_routine(action: str, activity?: str, location?: str, hours_back?: float) -> dict

Actions: "today" (today's log), "log" (record activity), "history" (past entries).
Builds a picture of normal patterns so deviations can trigger check-ins.
```

### weather_check
```
weather_check(location?: str) -> dict

Returns current weather + practical suggestions (bring umbrella, wear jacket).
Uses OpenWeatherMap API with fallback.
```

### call_emergency *(separate owner)*
```
call_emergency(reason: str) -> dict

Twilio voice call to emergency contact. Not implemented in this module.
```

---

## Prompts

### `prompts/main_agent_system.md`
The main agent personality and behavior. Defines the warm, patient caretaker persona.
Covers: Remind Me, Last Seen, Daily Awareness, communication rules, decision framework,
and tool usage guidelines. The agent reads this as its system message.

### `prompts/observer_system.md`
Used internally by the `analyze_frame` tool. Instructs the vision LLM on what to
track: objects, people, activity, danger signals. Defines the JSON output format.

---

## State Store Schema (SQLite)

```sql
CREATE TABLE observations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    raw_json    TEXT NOT NULL,
    summary     TEXT NOT NULL
);

CREATE TABLE object_states (
    item        TEXT PRIMARY KEY,
    location    TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    confidence  REAL
);

CREATE TABLE people_states (
    name        TEXT PRIMARY KEY,
    present     INTEGER NOT NULL,
    last_seen   TEXT NOT NULL,
    arrived_at  TEXT,
    departed_at TEXT
);

CREATE TABLE medications (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    dosage          TEXT NOT NULL,
    scheduled_times TEXT NOT NULL,  -- JSON array: ["08:00", "20:00"]
    notes           TEXT
);

CREATE TABLE medication_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    medication_name TEXT NOT NULL,
    scheduled_time  TEXT NOT NULL,
    taken_at        TEXT,
    skipped         INTEGER DEFAULT 0,
    date            TEXT NOT NULL
);

CREATE TABLE routine_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    activity    TEXT NOT NULL,
    location    TEXT,
    notes       TEXT
);

CREATE TABLE calendar_events (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    time        TEXT NOT NULL,
    end_time    TEXT,
    location    TEXT,
    notes       TEXT
);
```

---

## WebSocket Message Protocol

### Client → Server

| Message Type | Payload | Frequency |
|---|---|---|
| `frame` | `{ "image": "<base64 JPEG>" }` | 2-5 fps |
| `question` | `{ "text": "Where are my keys?" }` | On user speech |
| `ping` | `{}` | Every 30s |

### Server → Client

| Message Type | Payload | Trigger |
|---|---|---|
| `speech` | `{ "text": "...", "audio": "<base64 mp3>" }` | Agent response |
| `alert` | `{ "level": "info\|warn\|emergency", "message": "..." }` | Agent decision |
| `pong` | `{}` | Ping response |

---

## File Structure

```
multimodal/
├── ARCHITECTURE.md
├── .env.example
├── prompts/
│   ├── main_agent_system.md       # Main agent system prompt
│   └── observer_system.md         # Vision analysis prompt (used by analyze_frame tool)
├── server/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + WebSocket endpoint (TODO)
│   ├── agents/
│   │   ├── __init__.py
│   │   └── graph.py               # LangGraph agent graph
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── analyze_frame.py       # Vision analysis tool
│   │   ├── calendar_tool.py       # Calendar read/write
│   │   ├── speech.py              # TTS → WebSocket
│   │   ├── state_query.py         # AnswerQuestion + GetPreviousState
│   │   ├── medication.py          # Medication schedule + compliance
│   │   ├── routine.py             # Daily routine logging
│   │   ├── weather.py             # Weather conditions + advice
│   │   └── emergency.py           # CallEmergency (separate owner — Twilio)
│   ├── state/
│   │   ├── __init__.py
│   │   ├── store.py               # SQLite state store
│   │   └── models.py              # Pydantic models
│   ├── data/                      # Auto-created at runtime
│   │   └── state.db               # SQLite database
│   └── requirements.txt
└── ios/                           # Swift app (separate owner)
    └── AlzCare/
        └── ...
```

---

## Sequence: "Where are my keys?"

```
iOS App        WebSocket       LangGraph Agent        Tools              State Store
  │               │                 │                    │                    │
  │── question ──►│                 │                    │                    │
  │ "Where are    │── HumanMsg ───►│                    │                    │
  │  my keys?"    │                │ thinks: user wants  │                    │
  │               │                │ to find keys        │                    │
  │               │                │── answer_question ──►                    │
  │               │                │                    │── search objects ──►│
  │               │                │                    │◄── keys: hallway   │
  │               │                │◄── results ────────│    table           │
  │               │                │                    │                    │
  │               │                │── speech_tool ─────►                    │
  │               │◄── audio ──────│  "Your keys are    │                    │
  │◄── speech ────│                │   on the hallway   │                    │
  │               │                │   table."          │                    │
```

## Sequence: Proactive Medication Reminder

```
iOS App        WebSocket       LangGraph Agent        Tools              State Store
  │               │                 │                    │                    │
  │── frame ─────►│                 │                    │                    │
  │               │── HumanMsg ───►│                    │                    │
  │               │                │── analyze_frame ───►                    │
  │               │                │                    │── vision LLM ──►   │
  │               │                │◄── observation ────│                    │
  │               │                │                    │                    │
  │               │                │ thinks: user is in  │                    │
  │               │                │ kitchen, morning.   │                    │
  │               │                │ check meds?         │                    │
  │               │                │                    │                    │
  │               │                │── medication_check ►                    │
  │               │                │                    │── query schedule ─►│
  │               │                │◄── overdue: Aricept│                    │
  │               │                │                    │                    │
  │               │                │── speech_tool ─────►                    │
  │◄── speech ────│◄── audio ──────│ "Good morning! Don't│                   │
  │               │                │  forget your Aricept│                   │
  │               │                │  — it's on the     │                    │
  │               │                │  kitchen counter."  │                    │
```
