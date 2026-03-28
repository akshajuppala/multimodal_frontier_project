from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .models import (
    FrameObservation,
    MedicationEntry,
    MedicationLog,
    ObjectState,
    PersonState,
    RoutineEntry,
)

DB_PATH = Path(__file__).parent.parent / "data" / "state.db"


class StateStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        cur = self._conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS observations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                raw_json    TEXT NOT NULL,
                summary     TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS object_states (
                item        TEXT PRIMARY KEY,
                location    TEXT NOT NULL,
                last_seen   TEXT NOT NULL,
                confidence  REAL
            );

            CREATE TABLE IF NOT EXISTS people_states (
                name        TEXT PRIMARY KEY,
                present     INTEGER NOT NULL,
                last_seen   TEXT NOT NULL,
                arrived_at  TEXT,
                departed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS medications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                dosage          TEXT NOT NULL,
                scheduled_times TEXT NOT NULL,
                notes           TEXT
            );

            CREATE TABLE IF NOT EXISTS medication_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                medication_name TEXT NOT NULL,
                scheduled_time  TEXT NOT NULL,
                taken_at        TEXT,
                skipped         INTEGER DEFAULT 0,
                date            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS routine_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                activity    TEXT NOT NULL,
                location    TEXT,
                notes       TEXT
            );

            CREATE TABLE IF NOT EXISTS calendar_events (
                id          TEXT PRIMARY KEY,
                title       TEXT NOT NULL,
                time        TEXT NOT NULL,
                end_time    TEXT,
                location    TEXT,
                notes       TEXT
            );
        """)
        self._conn.commit()

    # --- Observations ---

    def save_observation(self, obs: FrameObservation) -> None:
        ts = (obs.timestamp or datetime.utcnow()).isoformat()
        summary_parts = []
        if obs.activity:
            summary_parts.append(obs.activity)
        for obj in obs.objects:
            summary_parts.append(f"{obj.item} {obj.action.value} at {obj.location}")
        if obs.danger:
            summary_parts.append(f"DANGER: {obs.danger.description}")
        summary = ". ".join(summary_parts) or "No notable changes."

        self._conn.execute(
            "INSERT INTO observations (timestamp, raw_json, summary) VALUES (?, ?, ?)",
            (ts, obs.model_dump_json(), summary),
        )

        for obj in obs.objects:
            self._conn.execute(
                """INSERT INTO object_states (item, location, last_seen, confidence)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(item) DO UPDATE SET
                     location=excluded.location,
                     last_seen=excluded.last_seen,
                     confidence=excluded.confidence""",
                (obj.item, obj.location, ts, obj.confidence),
            )

        if obs.people:
            for name in obs.people.present:
                self._conn.execute(
                    """INSERT INTO people_states (name, present, last_seen, arrived_at)
                       VALUES (?, 1, ?, ?)
                       ON CONFLICT(name) DO UPDATE SET
                         present=1, last_seen=excluded.last_seen""",
                    (name, ts, ts),
                )
            for name in obs.people.departed:
                self._conn.execute(
                    """INSERT INTO people_states (name, present, last_seen, departed_at)
                       VALUES (?, 0, ?, ?)
                       ON CONFLICT(name) DO UPDATE SET
                         present=0, last_seen=excluded.last_seen, departed_at=excluded.departed_at""",
                    (name, ts, ts),
                )
        self._conn.commit()

    def get_object_state(self, item: str) -> Optional[ObjectState]:
        row = self._conn.execute(
            "SELECT * FROM object_states WHERE item = ? COLLATE NOCASE", (item,)
        ).fetchone()
        if not row:
            return None
        return ObjectState(
            item=row["item"],
            location=row["location"],
            last_seen=datetime.fromisoformat(row["last_seen"]),
            confidence=row["confidence"] or 0.0,
        )

    def search_objects(self, query: str) -> list[ObjectState]:
        rows = self._conn.execute(
            "SELECT * FROM object_states WHERE item LIKE ? COLLATE NOCASE ORDER BY last_seen DESC",
            (f"%{query}%",),
        ).fetchall()
        return [
            ObjectState(
                item=r["item"],
                location=r["location"],
                last_seen=datetime.fromisoformat(r["last_seen"]),
                confidence=r["confidence"] or 0.0,
            )
            for r in rows
        ]

    def get_all_objects(self) -> list[ObjectState]:
        rows = self._conn.execute(
            "SELECT * FROM object_states ORDER BY last_seen DESC"
        ).fetchall()
        return [
            ObjectState(
                item=r["item"],
                location=r["location"],
                last_seen=datetime.fromisoformat(r["last_seen"]),
                confidence=r["confidence"] or 0.0,
            )
            for r in rows
        ]

    # --- People ---

    def get_person_state(self, name: str) -> Optional[PersonState]:
        row = self._conn.execute(
            "SELECT * FROM people_states WHERE name = ? COLLATE NOCASE", (name,)
        ).fetchone()
        if not row:
            return None
        return PersonState(
            name=row["name"],
            present=bool(row["present"]),
            last_seen=datetime.fromisoformat(row["last_seen"]),
            arrived_at=datetime.fromisoformat(row["arrived_at"]) if row["arrived_at"] else None,
            departed_at=datetime.fromisoformat(row["departed_at"]) if row["departed_at"] else None,
        )

    def get_present_people(self) -> list[PersonState]:
        rows = self._conn.execute(
            "SELECT * FROM people_states WHERE present = 1"
        ).fetchall()
        return [
            PersonState(
                name=r["name"],
                present=True,
                last_seen=datetime.fromisoformat(r["last_seen"]),
                arrived_at=datetime.fromisoformat(r["arrived_at"]) if r["arrived_at"] else None,
            )
            for r in rows
        ]

    # --- Observations history ---

    def get_observations(
        self, from_time: Optional[datetime] = None, to_time: Optional[datetime] = None, limit: int = 50
    ) -> list[dict]:
        query = "SELECT * FROM observations WHERE 1=1"
        params: list = []
        if from_time:
            query += " AND timestamp >= ?"
            params.append(from_time.isoformat())
        if to_time:
            query += " AND timestamp <= ?"
            params.append(to_time.isoformat())
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(query, params).fetchall()
        return [{"timestamp": r["timestamp"], "summary": r["summary"]} for r in rows]

    def search_observations(self, query: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM observations WHERE summary LIKE ? COLLATE NOCASE ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit),
        ).fetchall()
        return [{"timestamp": r["timestamp"], "summary": r["summary"]} for r in rows]

    # --- Medications ---

    def add_medication(self, med: MedicationEntry) -> int:
        cur = self._conn.execute(
            "INSERT INTO medications (name, dosage, scheduled_times, notes) VALUES (?, ?, ?, ?)",
            (med.name, med.dosage, json.dumps(med.scheduled_times), med.notes),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_medications(self) -> list[MedicationEntry]:
        rows = self._conn.execute("SELECT * FROM medications").fetchall()
        return [
            MedicationEntry(
                id=r["id"],
                name=r["name"],
                dosage=r["dosage"],
                scheduled_times=json.loads(r["scheduled_times"]),
                notes=r["notes"],
            )
            for r in rows
        ]

    def log_medication_taken(self, medication_name: str, scheduled_time: str) -> None:
        now = datetime.utcnow()
        self._conn.execute(
            "INSERT INTO medication_log (medication_name, scheduled_time, taken_at, date) VALUES (?, ?, ?, ?)",
            (medication_name, scheduled_time, now.isoformat(), now.date().isoformat()),
        )
        self._conn.commit()

    def get_medication_status_today(self) -> list[dict]:
        today = datetime.utcnow().date().isoformat()
        meds = self.get_medications()
        result = []
        for med in meds:
            for sched_time in med.scheduled_times:
                log = self._conn.execute(
                    "SELECT * FROM medication_log WHERE medication_name = ? AND scheduled_time = ? AND date = ?",
                    (med.name, sched_time, today),
                ).fetchone()
                result.append({
                    "medication": med.name,
                    "dosage": med.dosage,
                    "scheduled_time": sched_time,
                    "taken": log is not None,
                    "taken_at": log["taken_at"] if log else None,
                })
        return result

    # --- Routine ---

    def log_routine(self, entry: RoutineEntry) -> int:
        cur = self._conn.execute(
            "INSERT INTO routine_log (timestamp, activity, location, notes) VALUES (?, ?, ?, ?)",
            (entry.timestamp.isoformat(), entry.activity, entry.location, entry.notes),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_routine_today(self) -> list[RoutineEntry]:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM routine_log WHERE timestamp >= ? ORDER BY timestamp ASC",
            (today_start,),
        ).fetchall()
        return [
            RoutineEntry(
                id=r["id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                activity=r["activity"],
                location=r["location"],
                notes=r["notes"],
            )
            for r in rows
        ]

    def get_routine_range(self, from_time: datetime, to_time: datetime) -> list[RoutineEntry]:
        rows = self._conn.execute(
            "SELECT * FROM routine_log WHERE timestamp >= ? AND timestamp <= ? ORDER BY timestamp ASC",
            (from_time.isoformat(), to_time.isoformat()),
        ).fetchall()
        return [
            RoutineEntry(
                id=r["id"],
                timestamp=datetime.fromisoformat(r["timestamp"]),
                activity=r["activity"],
                location=r["location"],
                notes=r["notes"],
            )
            for r in rows
        ]

    # --- Calendar ---

    def save_calendar_event(self, event: dict) -> None:
        self._conn.execute(
            """INSERT INTO calendar_events (id, title, time, end_time, location, notes)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 title=excluded.title, time=excluded.time, end_time=excluded.end_time,
                 location=excluded.location, notes=excluded.notes""",
            (
                event.get("id", str(hash(event["title"] + event["time"]))),
                event["title"],
                event["time"],
                event.get("end_time"),
                event.get("location"),
                event.get("notes"),
            ),
        )
        self._conn.commit()

    def get_calendar_events(self, date: Optional[str] = None) -> list[dict]:
        if date:
            rows = self._conn.execute(
                "SELECT * FROM calendar_events WHERE time LIKE ? ORDER BY time ASC",
                (f"{date}%",),
            ).fetchall()
        else:
            today = datetime.utcnow().date().isoformat()
            rows = self._conn.execute(
                "SELECT * FROM calendar_events WHERE time LIKE ? ORDER BY time ASC",
                (f"{today}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
