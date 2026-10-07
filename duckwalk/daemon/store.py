"""SQLite `windows` table (schema in duckwalk.md, section 5)."""

import sqlite3

from duckwalk import config

FEATURES = ["mins_since_break", "failed_builds", "same_file_edits", "undo_ratio", "commits", "hour"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS windows (
  id               INTEGER PRIMARY KEY,
  ts               TIMESTAMP,
  repo             TEXT,
  mins_since_break REAL,
  failed_builds    INT,
  same_file_edits  INT,
  undo_ratio       REAL,
  commits          INT,
  hour             INT,
  nudged           BOOL,
  walked           BOOL,
  dismissed_fast   BOOL,   -- dismissed within 10s => false nudge
  resolved_30m     BOOL,   -- auto-labeled: test passed or commit landed
  stuck            BOOL    -- hand label: 1 stuck, 0 flow, NULL unlabeled
);
"""


def connect(path=None) -> sqlite3.Connection:
    path = path or config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def insert_window(conn: sqlite3.Connection, window: dict) -> int:
    cols = ["ts", "repo", *FEATURES]
    cur = conn.execute(
        f"INSERT INTO windows ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
        [window[c] for c in cols],
    )
    conn.commit()
    return cur.lastrowid


def labeled(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM windows WHERE stuck IS NOT NULL ORDER BY ts").fetchall()
