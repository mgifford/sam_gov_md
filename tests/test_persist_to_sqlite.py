"""Tests for persist_to_sqlite.py."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import persist_to_sqlite as pst


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

class TestInitDb:
    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(":memory:")

    def test_creates_opportunities_table(self) -> None:
        conn = self._connect()
        pst.init_db(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "opportunities" in tables
        conn.close()

    def test_creates_opportunity_sightings_table(self) -> None:
        conn = self._connect()
        pst.init_db(conn)
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "opportunity_sightings" in tables
        conn.close()

    def test_idempotent_second_call(self) -> None:
        conn = self._connect()
        pst.init_db(conn)
        # Should not raise even when called twice.
        pst.init_db(conn)
        conn.close()

    def test_creates_agency_index(self) -> None:
        conn = self._connect()
        pst.init_db(conn)
        indices = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_opportunities_agency" in indices
        conn.close()

    def test_creates_type_index(self) -> None:
        conn = self._connect()
        pst.init_db(conn)
        indices = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "idx_opportunities_type" in indices
        conn.close()

    def test_migration_adds_columns_when_missing(self) -> None:
        """init_db should tolerate pre-existing tables without description/matches/awardee."""
        conn = self._connect()
        # Simulate a legacy table without the new columns but with the indexed ones.
        conn.execute(
            """
            CREATE TABLE opportunities (
                notice_id TEXT PRIMARY KEY,
                title TEXT,
                agency TEXT,
                notice_type TEXT,
                first_seen_date TEXT NOT NULL,
                last_seen_date TEXT NOT NULL,
                seen_count INTEGER NOT NULL DEFAULT 1,
                last_snapshot_date TEXT NOT NULL,
                is_win INTEGER NOT NULL
            )
            """
        )
        # Should not raise; columns added via ALTER TABLE.
        pst.init_db(conn)
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(opportunities)").fetchall()
        }
        assert "description" in cols
        assert "matches" in cols
        assert "awardee" in cols
        conn.close()


# ---------------------------------------------------------------------------
# upsert_record
# ---------------------------------------------------------------------------

def _make_row(notice_id: str = "N001", notice_type: str = "Solicitation") -> dict:
    return {
        "NoticeId": notice_id,
        "Sol#": "SOL-001",
        "Title": "Test Opportunity",
        "Department/Ind.Agency": "Test Agency",
        "Type": notice_type,
        "PostedDate": "2024-03-15",
        "ResponseDeadLine": "2024-04-15",
        "NaicsCode": "541512",
        "Link": "https://sam.gov/opp/" + notice_id,
        "Description": "A test description.",
        "matches": [{"term": "web", "count": 3}],
        "Awardee": "",
    }


class TestUpsertRecord:
    def _setup(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        pst.init_db(conn)
        return conn

    def test_insert_new_record_returns_inserted(self) -> None:
        conn = self._setup()
        result = pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        assert result == "inserted"
        conn.close()

    def test_update_existing_record_returns_updated(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        result = pst.upsert_record(conn, _make_row("N001"), "2024-03-16")
        assert result == "updated"
        conn.close()

    def test_missing_notice_id_returns_skipped(self) -> None:
        conn = self._setup()
        row = _make_row()
        row["NoticeId"] = ""
        result = pst.upsert_record(conn, row, "2024-03-15")
        assert result == "skipped"
        conn.close()

    def test_seen_count_incremented_on_duplicate(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        pst.upsert_record(conn, _make_row("N001"), "2024-03-16")
        row = conn.execute(
            "SELECT seen_count FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()
        assert row[0] == 2
        conn.close()

    def test_is_win_flag_set_for_award_type(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001", "Award Notice"), "2024-03-15")
        row = conn.execute(
            "SELECT is_win FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()
        assert row[0] == 1
        conn.close()

    def test_is_win_flag_zero_for_non_award(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001", "Solicitation"), "2024-03-15")
        row = conn.execute(
            "SELECT is_win FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()
        assert row[0] == 0
        conn.close()

    def test_description_truncated_to_1000_chars(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["Description"] = "X" * 2000
        pst.upsert_record(conn, row, "2024-03-15")
        stored = conn.execute(
            "SELECT description FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert len(stored) == 1000
        conn.close()

    def test_matches_stored_as_json(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["matches"] = [{"term": "api", "count": 5}]
        pst.upsert_record(conn, row, "2024-03-15")
        stored = conn.execute(
            "SELECT matches FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        parsed = json.loads(stored)
        assert parsed[0]["term"] == "api"
        conn.close()

    def test_matches_truncated_to_10_items(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["matches"] = [{"term": f"term{i}", "count": i} for i in range(15)]
        pst.upsert_record(conn, row, "2024-03-15")
        stored = json.loads(
            conn.execute(
                "SELECT matches FROM opportunities WHERE notice_id = ?", ("N001",)
            ).fetchone()[0]
        )
        assert len(stored) == 10
        conn.close()

    def test_sighting_recorded(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        count = conn.execute(
            "SELECT COUNT(*) FROM opportunity_sightings WHERE notice_id = ?",
            ("N001",),
        ).fetchone()[0]
        assert count == 1
        conn.close()

    def test_sighting_not_duplicated_for_same_date(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        count = conn.execute(
            "SELECT COUNT(*) FROM opportunity_sightings WHERE notice_id = ?",
            ("N001",),
        ).fetchone()[0]
        assert count == 1
        conn.close()

    def test_awardee_stored(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["Awardee"] = "ACME Corp"
        pst.upsert_record(conn, row, "2024-03-15")
        stored = conn.execute(
            "SELECT awardee FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored == "ACME Corp"
        conn.close()

    def test_empty_awardee_stored_as_none(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        stored = conn.execute(
            "SELECT awardee FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored is None
        conn.close()

    def test_whitespace_only_notice_id_returns_skipped(self) -> None:
        conn = self._setup()
        row = _make_row()
        row["NoticeId"] = "   "
        result = pst.upsert_record(conn, row, "2024-03-15")
        assert result == "skipped"
        conn.close()

    def test_award_date_stored(self) -> None:
        conn = self._setup()
        row = _make_row("N001", "Award Notice")
        row["AwardDate"] = "2024-06-01"
        pst.upsert_record(conn, row, "2024-06-01")
        stored = conn.execute(
            "SELECT award_date FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored == "2024-06-01"
        conn.close()

    def test_empty_award_date_stored_as_none(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["AwardDate"] = ""
        pst.upsert_record(conn, row, "2024-03-15")
        stored = conn.execute(
            "SELECT award_date FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored is None
        conn.close()

    def test_contract_officer_stored(self) -> None:
        conn = self._setup()
        row = _make_row("N001")
        row["PrimaryContactFullname"] = "Jane Doe"
        pst.upsert_record(conn, row, "2024-03-15")
        stored = conn.execute(
            "SELECT contract_officer FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored == "Jane Doe"
        conn.close()

    def test_missing_contract_officer_stored_as_none(self) -> None:
        conn = self._setup()
        pst.upsert_record(conn, _make_row("N001"), "2024-03-15")
        stored = conn.execute(
            "SELECT contract_officer FROM opportunities WHERE notice_id = ?", ("N001",)
        ).fetchone()[0]
        assert stored is None
        conn.close()
