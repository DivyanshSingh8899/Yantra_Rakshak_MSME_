"""SQLite persistence for health events and advisories (fully local / offline)."""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).parent / "yantra.db"

_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_conn = _connect()


def init_db() -> None:
    with _lock:
        _conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id   TEXT    NOT NULL,
                machine_type TEXT,
                location     TEXT,
                ts           TEXT    NOT NULL,
                fault_type   TEXT,
                severity     TEXT,
                confidence   REAL,
                mse_score    REAL,
                rpm          INTEGER,
                features     TEXT,
                waveform     TEXT,
                advisory     TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_events_machine ON events(machine_id);
            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);
            """
        )
        _conn.commit()


def insert_event(event: dict[str, Any], advisory: Optional[dict[str, Any]]) -> int:
    with _lock:
        cur = _conn.execute(
            """
            INSERT INTO events
              (machine_id, machine_type, location, ts, fault_type, severity,
               confidence, mse_score, rpm, features, waveform, advisory)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                event["machine_id"],
                event.get("machine_type"),
                event.get("location"),
                event["ts"],
                event.get("fault_type"),
                event.get("severity"),
                event.get("confidence"),
                event.get("mse_score"),
                event.get("rpm"),
                json.dumps(event.get("features")),
                json.dumps(event.get("waveform", [])),
                json.dumps(advisory) if advisory else None,
            ),
        )
        _conn.commit()
        return int(cur.lastrowid)


def update_advisory(event_id: int, advisory: dict[str, Any]) -> None:
    with _lock:
        _conn.execute(
            "UPDATE events SET advisory = ? WHERE id = ?",
            (json.dumps(advisory), event_id),
        )
        _conn.commit()


def _row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    d = dict(row)
    d["features"] = json.loads(d["features"]) if d.get("features") else None
    d["waveform"] = json.loads(d["waveform"]) if d.get("waveform") else []
    d["advisory"] = json.loads(d["advisory"]) if d.get("advisory") else None
    return d


def recent_alerts(limit: int = 50) -> list[dict[str, Any]]:
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM events WHERE severity != 'OK' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_event(r) for r in rows]


def machine_history(machine_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with _lock:
        rows = _conn.execute(
            "SELECT * FROM events WHERE machine_id = ? ORDER BY id DESC LIMIT ?",
            (machine_id, limit),
        ).fetchall()
    return [_row_to_event(r) for r in reversed(rows)]


def counts_for(machine_id: str) -> tuple[int, int]:
    with _lock:
        total = _conn.execute(
            "SELECT COUNT(*) FROM events WHERE machine_id = ?", (machine_id,)
        ).fetchone()[0]
        alerts = _conn.execute(
            "SELECT COUNT(*) FROM events WHERE machine_id = ? AND severity != 'OK'",
            (machine_id,),
        ).fetchone()[0]
    return int(total), int(alerts)


def fleet_stats() -> dict[str, int]:
    with _lock:
        total = _conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        alerts = _conn.execute(
            "SELECT COUNT(*) FROM events WHERE severity != 'OK'"
        ).fetchone()[0]
        critical = _conn.execute(
            "SELECT COUNT(*) FROM events WHERE severity = 'CRITICAL'"
        ).fetchone()[0]
    return {"events": int(total), "alerts": int(alerts), "critical": int(critical)}
