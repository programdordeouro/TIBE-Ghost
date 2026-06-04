import os
import sqlite3
from datetime import datetime
from pathlib import Path

# Vercel (and other serverless): use /tmp — project dir is read-only at runtime.
# VERCEL env var is injected automatically by the platform.
_local_db = str(Path(__file__).parent / "ghost.db")
_default_db = "/tmp/ghost.db" if (os.getenv("VERCEL") or not os.access(str(Path(__file__).parent), os.W_OK)) else _local_db
DB_PATH = Path(os.getenv("DB_PATH", _default_db))


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                session_id TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                relevance_score REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS simulations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                topic TEXT NOT NULL,
                cost_analysis TEXT NOT NULL,
                risk_analysis TEXT NOT NULL,
                return_analysis TEXT NOT NULL
            );
        """)


def save_message(role: str, content: str, session_id: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO memories (timestamp, role, content, session_id) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), role, content, session_id),
        )


def get_last_n_messages(n: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT timestamp, role, content, session_id FROM memories ORDER BY id DESC LIMIT ?",
            (n,),
        ).fetchall()
    rows.reverse()
    return [{"timestamp": r[0], "role": r[1], "content": r[2], "session_id": r[3]} for r in rows]


def get_profile() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT key, value FROM profile").fetchall()
    return {r[0]: r[1] for r in rows}


def save_profile(key: str, value: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO profile (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, datetime.now().isoformat()),
        )


def save_opportunity(title: str, description: str, score: float):
    with _conn() as c:
        c.execute(
            "INSERT INTO opportunities (timestamp, title, description, relevance_score) VALUES (?, ?, ?, ?)",
            (datetime.now().isoformat(), title, description, score),
        )


def get_opportunities(limit: int = 10) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT timestamp, title, description, relevance_score FROM opportunities "
            "ORDER BY relevance_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [{"timestamp": r[0], "title": r[1], "description": r[2], "score": r[3]} for r in rows]


def save_simulation(topic: str, cost: str, risk: str, ret: str):
    with _conn() as c:
        c.execute(
            "INSERT INTO simulations (timestamp, topic, cost_analysis, risk_analysis, return_analysis) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), topic, cost, risk, ret),
        )


def count_sessions() -> int:
    with _conn() as c:
        row = c.execute("SELECT COUNT(DISTINCT session_id) FROM memories").fetchone()
    return row[0] if row else 0


init_db()
