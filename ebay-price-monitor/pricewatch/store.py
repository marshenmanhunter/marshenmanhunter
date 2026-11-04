"""SQLite history: one row per scan, one row per listing seen, one row per alert sent.

No seller usernames or buyer data are stored. Only item ID, title, URL, condition and price.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Iterable

from .listing import Listing
from .stats import Summary

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_key TEXT NOT NULL,
    ts TEXT NOT NULL,
    total_available INTEGER,
    sample_size INTEGER,
    complete INTEGER,
    median REAL, p10 REAL, p25 REAL, p75 REAL, p90 REAL,
    min REAL, max REAL, mad REAL
);
CREATE INDEX IF NOT EXISTS idx_runs_item_ts ON runs(item_key, ts);

CREATE TABLE IF NOT EXISTS listings (
    item_key TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT,
    url TEXT,
    condition TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    first_total REAL,
    last_total REAL,
    gone_at TEXT,
    PRIMARY KEY (item_key, item_id)
);
CREATE INDEX IF NOT EXISTS idx_listings_gone ON listings(item_key, gone_at);

CREATE TABLE IF NOT EXISTS alerts (
    item_key TEXT NOT NULL,
    item_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    total REAL NOT NULL,
    ts TEXT NOT NULL,
    PRIMARY KEY (item_key, item_id, kind)
);
"""

# Re-alert on a listing we already flagged only when its price drops by at least this share.
REALERT_DROP = 0.03


class Store:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # --- writes -------------------------------------------------------------

    def record_run(
        self,
        item_key: str,
        ts: datetime,
        total_available: int,
        sample_size: int,
        complete: bool,
        s: Summary | None,
    ) -> None:
        vals = (s.median, s.p10, s.p25, s.p75, s.p90, s.min, s.max, s.mad) if s else (None,) * 8
        self.conn.execute(
            "INSERT INTO runs (item_key, ts, total_available, sample_size, complete,"
            " median, p10, p25, p75, p90, min, max, mad) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (item_key, ts.isoformat(), total_available, sample_size, int(complete), *vals),
        )
        self.conn.commit()

    def upsert_listings(self, item_key: str, listings: Iterable[Listing], ts: datetime) -> None:
        now = ts.isoformat()
        self.conn.executemany(
            """
            INSERT INTO listings (item_key, item_id, title, url, condition,
                                  first_seen, last_seen, first_total, last_total, gone_at)
            VALUES (?,?,?,?,?,?,?,?,?,NULL)
            ON CONFLICT(item_key, item_id) DO UPDATE SET
                title=excluded.title, url=excluded.url, condition=excluded.condition,
                last_seen=excluded.last_seen, last_total=excluded.last_total, gone_at=NULL
            """,
            [
                (item_key, l.item_id, l.title, l.url, l.condition, now, now, l.total, l.total)
                for l in listings
            ],
        )
        self.conn.commit()

    def mark_gone(self, item_key: str, seen_ids: set[str], ts: datetime) -> int:
        """Mark tracked listings missing from a complete scan as gone. Returns how many."""
        rows = self.conn.execute(
            "SELECT item_id FROM listings WHERE item_key=? AND gone_at IS NULL", (item_key,)
        ).fetchall()
        gone = [(ts.isoformat(), item_key, r["item_id"]) for r in rows if r["item_id"] not in seen_ids]
        self.conn.executemany(
            "UPDATE listings SET gone_at=? WHERE item_key=? AND item_id=?", gone
        )
        self.conn.commit()
        return len(gone)

    def should_alert(self, item_key: str, item_id: str, kind: str, total: float, ts: datetime) -> bool:
        """True for a new alert or a further price drop. Records the alert when True."""
        row = self.conn.execute(
            "SELECT total FROM alerts WHERE item_key=? AND item_id=? AND kind=?",
            (item_key, item_id, kind),
        ).fetchone()
        if row and total > row["total"] * (1 - REALERT_DROP):
            return False
        self.conn.execute(
            "INSERT OR REPLACE INTO alerts (item_key, item_id, kind, total, ts) VALUES (?,?,?,?,?)",
            (item_key, item_id, kind, total, ts.isoformat()),
        )
        self.conn.commit()
        return True

    # --- reads --------------------------------------------------------------

    def gone_totals(self, item_key: str, since: datetime) -> list[float]:
        rows = self.conn.execute(
            "SELECT last_total FROM listings WHERE item_key=? AND gone_at >= ?",
            (item_key, since.isoformat()),
        ).fetchall()
        return [r["last_total"] for r in rows if r["last_total"] is not None]

    def runs(self, item_key: str, since: datetime | None = None) -> list[sqlite3.Row]:
        q = "SELECT * FROM runs WHERE item_key=?"
        args: list = [item_key]
        if since:
            q += " AND ts >= ?"
            args.append(since.isoformat())
        return self.conn.execute(q + " ORDER BY ts", args).fetchall()

    def cheapest_active(self, item_key: str, limit: int = 3) -> list[sqlite3.Row]:
        last = self.conn.execute(
            "SELECT MAX(last_seen) AS ts FROM listings WHERE item_key=?", (item_key,)
        ).fetchone()["ts"]
        if not last:
            return []
        return self.conn.execute(
            "SELECT * FROM listings WHERE item_key=? AND gone_at IS NULL AND last_seen=?"
            " ORDER BY last_total LIMIT ?",
            (item_key, last, limit),
        ).fetchall()
