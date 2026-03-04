#!/usr/bin/env python3
"""Persist daily opportunity snapshot to SQLite with dedup and history."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunities (
            notice_id TEXT PRIMARY KEY,
            sol_number TEXT,
            title TEXT,
            agency TEXT,
            notice_type TEXT,
            posted_date TEXT,
            response_deadline TEXT,
            naics_code TEXT,
            link TEXT,
            is_win INTEGER NOT NULL,
            first_seen_date TEXT NOT NULL,
            last_seen_date TEXT NOT NULL,
            seen_count INTEGER NOT NULL DEFAULT 1,
            last_snapshot_date TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS opportunity_sightings (
            notice_id TEXT NOT NULL,
            snapshot_date TEXT NOT NULL,
            seen_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (notice_id, snapshot_date)
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunities_agency ON opportunities (agency)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_opportunities_type ON opportunities (notice_type)
        """
    )


def upsert_record(conn: sqlite3.Connection, row: dict, snapshot_date: str) -> str:
    notice_id = (row.get("NoticeId") or "").strip()
    if not notice_id:
        return "skipped"

    existing = conn.execute(
        "SELECT notice_id FROM opportunities WHERE notice_id = ?", (notice_id,)
    ).fetchone()

    is_win = 1 if ("award" in (row.get("Type") or "").lower() or "win" in (row.get("Type") or "").lower()) else 0

    conn.execute(
        """
        INSERT INTO opportunities (
            notice_id, sol_number, title, agency, notice_type, posted_date,
            response_deadline, naics_code, link, is_win, first_seen_date,
            last_seen_date, seen_count, last_snapshot_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(notice_id) DO UPDATE SET
            sol_number = excluded.sol_number,
            title = excluded.title,
            agency = excluded.agency,
            notice_type = excluded.notice_type,
            posted_date = excluded.posted_date,
            response_deadline = excluded.response_deadline,
            naics_code = excluded.naics_code,
            link = excluded.link,
            is_win = excluded.is_win,
            last_seen_date = excluded.last_seen_date,
            last_snapshot_date = excluded.last_snapshot_date,
            seen_count = opportunities.seen_count + 1
        """,
        (
            notice_id,
            row.get("Sol#"),
            row.get("Title"),
            row.get("Department/Ind.Agency"),
            row.get("Type"),
            row.get("PostedDate"),
            row.get("ResponseDeadLine"),
            row.get("NaicsCode"),
            row.get("Link"),
            is_win,
            snapshot_date,
            snapshot_date,
            snapshot_date,
        ),
    )

    conn.execute(
        """
        INSERT OR IGNORE INTO opportunity_sightings (notice_id, snapshot_date)
        VALUES (?, ?)
        """,
        (notice_id, snapshot_date),
    )

    return "updated" if existing else "inserted"


def main() -> None:
    parser = argparse.ArgumentParser(description="Persist opportunity snapshot to SQLite")
    parser.add_argument("--records", default="data/today/records.json")
    parser.add_argument("--summary", default="data/today/summary.json")
    parser.add_argument("--db", default="data/opportunities.sqlite")
    parser.add_argument("--output", default="data/today/persistence_summary.json")
    args = parser.parse_args()

    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    summary = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    snapshot_date = summary.get("effective_date") or summary.get("requested_date")

    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    inserted = 0
    updated = 0
    skipped = 0

    with sqlite3.connect(db_path) as conn:
        init_db(conn)
        for row in records:
            state = upsert_record(conn, row, snapshot_date)
            if state == "inserted":
                inserted += 1
            elif state == "updated":
                updated += 1
            else:
                skipped += 1
        conn.commit()

        total_unique = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        total_sightings = conn.execute("SELECT COUNT(*) FROM opportunity_sightings").fetchone()[0]

    payload = {
        "snapshot_date": snapshot_date,
        "records_in_snapshot": len(records),
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total_unique_opportunities": total_unique,
        "total_sightings": total_sightings,
        "db_path": str(db_path),
    }

    Path(args.output).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
