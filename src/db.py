"""SQLite schema and helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "news.db"
RAW_DIR = DATA_DIR / "raw_html"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          INTEGER PRIMARY KEY,
    category    INTEGER NOT NULL,
    title       TEXT    NOT NULL,
    publish_date TEXT   NOT NULL,
    url         TEXT    NOT NULL,
    html_path   TEXT,
    fetched_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(publish_date);
CREATE INDEX IF NOT EXISTS idx_articles_cat  ON articles(category);

CREATE TABLE IF NOT EXISTS activities (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id   INTEGER NOT NULL,
    seq          INTEGER NOT NULL,
    name         TEXT    NOT NULL,
    start_dt     TEXT,
    end_dt       TEXT,
    description  TEXT,
    reward       TEXT,
    note         TEXT,
    kind         TEXT,        -- festival / recharge / weekly / pvp / version / mall / other
    keywords     TEXT,        -- comma list
    FOREIGN KEY (article_id) REFERENCES articles(id),
    UNIQUE (article_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_activities_name ON activities(name);
CREATE INDEX IF NOT EXISTS idx_activities_kind ON activities(kind);

CREATE TABLE IF NOT EXISTS recharge_gifts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id   INTEGER NOT NULL,
    activity_id  INTEGER,
    threshold    INTEGER,        -- e.g. 5000
    gift_name    TEXT NOT NULL,
    gift_qty     INTEGER,
    period_start TEXT,
    period_end   TEXT,
    raw_text     TEXT,
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS scrape_state (
    key     TEXT PRIMARY KEY,
    value   TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT,                       -- optional display name
    contact      TEXT,                       -- optional email/discord/etc
    message      TEXT    NOT NULL,
    submitted_at TEXT    NOT NULL,
    ip           TEXT,                       -- truncated (last octet zeroed)
    user_agent   TEXT,
    is_spam      INTEGER NOT NULL DEFAULT 0  -- soft-delete / hide flag
);
CREATE INDEX IF NOT EXISTS idx_feedback_time ON feedback(submitted_at);
"""


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def connect() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_schema() -> None:
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def cursor():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_state(key: str, default: str | None = None) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM scrape_state WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_state(key: str, value: str) -> None:
    with cursor() as conn:
        conn.execute(
            "INSERT INTO scrape_state(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
