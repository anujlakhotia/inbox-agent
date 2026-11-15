from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

DB_PATH = Path(os.getenv("DB_PATH", "data/agent.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS emails (
    id TEXT PRIMARY KEY,
    thread_id TEXT,
    sender TEXT,
    sender_email TEXT,
    subject TEXT,
    date TEXT,            -- ISO 8601
    snippet TEXT,
    body TEXT,
    section TEXT,         -- ai_business | growth | important | skip
    score REAL,           -- 0-10 relevance from the model
    summary TEXT,
    why TEXT,
    topics TEXT           -- comma separated
);
CREATE TABLE IF NOT EXISTS weights (
    key TEXT PRIMARY KEY, -- "sender:a@b.com" or "topic:agents"
    value REAL NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS emails_fts USING fts5(id UNINDEXED, subject, sender, body);
"""


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.executescript(SCHEMA)


def known_ids() -> set[str]:
    with conn() as c:
        return {r["id"] for r in c.execute("SELECT id FROM emails")}


def upsert_email(e: dict):
    with conn() as c:
        c.execute(
            """INSERT OR IGNORE INTO emails
               (id, thread_id, sender, sender_email, subject, date, snippet, body)
               VALUES (:id, :thread_id, :sender, :sender_email, :subject, :date, :snippet, :body)""",
            e,
        )
        c.execute(
            "INSERT INTO emails_fts (id, subject, sender, body) SELECT :id, :subject, :sender, :body "
            "WHERE NOT EXISTS (SELECT 1 FROM emails_fts WHERE id = :id)",
            e,
        )


def unclassified(limit: int = 200) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM emails WHERE section IS NULL ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def set_classification(email_id: str, section: str, score: float, summary: str, why: str, topics: list[str]):
    with conn() as c:
        c.execute(
            "UPDATE emails SET section=?, score=?, summary=?, why=?, topics=? WHERE id=?",
            (section, score, summary, why, ",".join(topics), email_id),
        )


def recent_classified(days: int) -> list[dict]:
    with conn() as c:
        rows = c.execute(
            "SELECT id, thread_id, sender, sender_email, subject, date, summary, why, topics, section, score "
            "FROM emails WHERE section IS NOT NULL AND section != 'skip' "
            "AND date >= datetime('now', ?)",
            (f"-{days} days",),
        ).fetchall()
    return [dict(r) for r in rows]


def get_weights() -> dict[str, float]:
    with conn() as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key, value FROM weights")}


def add_weight(key: str, delta: float):
    with conn() as c:
        c.execute(
            "INSERT INTO weights (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = value + excluded.value",
            (key, delta),
        )


def delete_weight(key: str):
    with conn() as c:
        c.execute("DELETE FROM weights WHERE key = ?", (key,))


def get_email(email_id: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT * FROM emails WHERE id = ?", (email_id,)).fetchone()
    return dict(r) if r else None


def search(question: str, limit: int = 8) -> list[dict]:
    """Full-text search over stored emails; falls back to the most recent ones."""
    words = [w for w in re.findall(r"[A-Za-z0-9]{3,}", question.lower())][:12]
    rows = []
    with conn() as c:
        if words:
            q = " OR ".join(f'"{w}"' for w in words)
            rows = c.execute(
                "SELECT e.* FROM emails_fts f JOIN emails e ON e.id = f.id "
                "WHERE emails_fts MATCH ? ORDER BY rank LIMIT ?",
                (q, limit),
            ).fetchall()
        if not rows:
            rows = c.execute("SELECT * FROM emails ORDER BY date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def search_emails(query: str, days: int | None = None, limit: int = 8) -> list[dict]:
    """Keyword search (no fallback to 'recent'), optionally limited to the last N days."""
    words = re.findall(r"[A-Za-z0-9]{2,}", query.lower())[:12]
    if not words:
        return []
    q = " OR ".join(f'"{w}"' for w in words)
    sql = "SELECT e.* FROM emails_fts f JOIN emails e ON e.id = f.id WHERE emails_fts MATCH ?"
    args: list = [q]
    if days:
        sql += " AND e.date >= datetime('now', ?)"
        args.append(f"-{days} days")
    with conn() as c:
        rows = c.execute(sql + " ORDER BY rank LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]


def by_sender(sender: str, limit: int = 8) -> list[dict]:
    like = f"%{sender.lower()}%"
    with conn() as c:
        rows = c.execute(
            "SELECT * FROM emails WHERE lower(sender) LIKE ? OR sender_email LIKE ? ORDER BY date DESC LIMIT ?",
            (like, like, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def recent(days: int = 3, section: str | None = None, limit: int = 15) -> list[dict]:
    sql = "SELECT * FROM emails WHERE date >= datetime('now', ?)"
    args: list = [f"-{days} days"]
    if section:
        sql += " AND section = ?"
        args.append(section)
    with conn() as c:
        rows = c.execute(sql + " ORDER BY date DESC LIMIT ?", (*args, limit)).fetchall()
    return [dict(r) for r in rows]
