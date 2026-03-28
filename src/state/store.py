"""SQLite-backed persistent store for medications, routine log, and object history.

Complements the in-memory SharedContext — SharedContext handles fast
real-time state, this store handles data that should survive restarts.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/state.db")

_instance: Optional["PersistentStore"] = None


def get_store() -> "PersistentStore":
    global _instance
    if _instance is None:
        _instance = PersistentStore()
    return _instance


class PersistentStore:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self) -> None:
        self._conn.executescript("""
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
                date            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS routine_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT NOT NULL,
                activity    TEXT NOT NULL,
                location    TEXT,
                notes       TEXT
            );
        """)
        self._conn.commit()

    # --- Medications ---

    def add_medication(self, name: str, dosage: str, scheduled_times: list[str], notes: str = "") -> int:
        cur = self._conn.execute(
            "INSERT INTO medications (name, dosage, scheduled_times, notes) VALUES (?, ?, ?, ?)",
            (name, dosage, json.dumps(scheduled_times), notes),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_medications(self) -> list[dict]:
        rows = self._conn.execute("SELECT * FROM medications").fetchall()
        return [
            {
                "id": r["id"],
                "name": r["name"],
                "dosage": r["dosage"],
                "scheduled_times": json.loads(r["scheduled_times"]),
                "notes": r["notes"],
            }
            for r in rows
        ]

    def log_medication_taken(self, medication_name: str, scheduled_time: str) -> None:
        now = datetime.now(timezone.utc)
        self._conn.execute(
            "INSERT INTO medication_log (medication_name, scheduled_time, taken_at, date) VALUES (?, ?, ?, ?)",
            (medication_name, scheduled_time, now.isoformat(), now.date().isoformat()),
        )
        self._conn.commit()

    def get_medication_status_today(self) -> list[dict]:
        today = datetime.now(timezone.utc).date().isoformat()
        meds = self.get_medications()
        result = []
        for med in meds:
            for sched_time in med["scheduled_times"]:
                log = self._conn.execute(
                    "SELECT * FROM medication_log WHERE medication_name = ? AND scheduled_time = ? AND date = ?",
                    (med["name"], sched_time, today),
                ).fetchone()
                result.append({
                    "medication": med["name"],
                    "dosage": med["dosage"],
                    "scheduled_time": sched_time,
                    "taken": log is not None,
                    "taken_at": log["taken_at"] if log else None,
                })
        return result

    # --- Routine ---

    def log_routine(self, activity: str, location: str | None = None, notes: str | None = None) -> int:
        now = datetime.now(timezone.utc)
        cur = self._conn.execute(
            "INSERT INTO routine_log (timestamp, activity, location, notes) VALUES (?, ?, ?, ?)",
            (now.isoformat(), activity, location, notes),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def get_routine_today(self) -> list[dict]:
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM routine_log WHERE timestamp >= ? ORDER BY timestamp ASC",
            (today_start,),
        ).fetchall()
        return [
            {
                "time": datetime.fromisoformat(r["timestamp"]).strftime("%I:%M %p"),
                "activity": r["activity"],
                "location": r["location"],
            }
            for r in rows
        ]

    def get_routine_range(self, hours_back: float) -> list[dict]:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours_back)).isoformat()
        rows = self._conn.execute(
            "SELECT * FROM routine_log WHERE timestamp >= ? ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()
        return [
            {
                "time": datetime.fromisoformat(r["timestamp"]).strftime("%I:%M %p"),
                "activity": r["activity"],
                "location": r["location"],
            }
            for r in rows
        ]

    def close(self) -> None:
        self._conn.close()
