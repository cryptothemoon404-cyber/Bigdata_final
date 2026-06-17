"""
Database module - SQLite with time-series sentiment data
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.getenv("DB_PATH", "data/sentiment.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sentiment_records (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol      TEXT    NOT NULL,
            source      TEXT    NOT NULL,
            headline    TEXT,
            score       REAL    NOT NULL,
            label       TEXT    NOT NULL,
            url         TEXT,
            collected_at TEXT   NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_symbol_time
            ON sentiment_records(symbol, collected_at);

        CREATE TABLE IF NOT EXISTS sentiment_aggregates (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol          TEXT    NOT NULL,
            window_start    TEXT    NOT NULL,
            window_end      TEXT    NOT NULL,
            avg_score       REAL,
            positive_count  INTEGER,
            negative_count  INTEGER,
            neutral_count   INTEGER,
            total_count     INTEGER,
            computed_at     TEXT    NOT NULL,
            UNIQUE(symbol, window_start)
        );

        CREATE TABLE IF NOT EXISTS api_usage (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            api_key     TEXT    NOT NULL,
            endpoint    TEXT,
            called_at   TEXT    NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    print(f"[DB] Initialized at {DB_PATH}")
