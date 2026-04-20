"""Tests for time_to_award.py."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

import time_to_award as tta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Return an in-memory SQLite connection with the opportunities schema."""
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """
        CREATE TABLE opportunities (
            notice_id TEXT PRIMARY KEY,
            sol_number TEXT,
            title TEXT,
            agency TEXT,
            notice_type TEXT,
            posted_date TEXT,
            response_deadline TEXT,
            naics_code TEXT,
            link TEXT,
            is_win INTEGER NOT NULL DEFAULT 0,
            first_seen_date TEXT NOT NULL DEFAULT '',
            last_seen_date TEXT NOT NULL DEFAULT '',
            seen_count INTEGER NOT NULL DEFAULT 1,
            last_snapshot_date TEXT NOT NULL DEFAULT '',
            description TEXT,
            matches TEXT,
            awardee TEXT,
            set_aside TEXT,
            additional_info_link TEXT,
            award_date TEXT,
            contract_officer TEXT
        )
        """
    )
    return conn


def _insert(conn: sqlite3.Connection, **kwargs: object) -> None:
    defaults = {
        "notice_id": "N001",
        "sol_number": "SOL-001",
        "title": "Test Opportunity",
        "agency": "Test Agency",
        "notice_type": "Solicitation",
        "posted_date": "2024-01-01",
        "last_seen_date": "2024-01-01",
        "is_win": 0,
        "award_date": None,
        "contract_officer": None,
        "awardee": None,
    }
    defaults.update(kwargs)
    conn.execute(
        """
        INSERT INTO opportunities
            (notice_id, sol_number, title, agency, notice_type, posted_date,
             last_seen_date, is_win, award_date, contract_officer, awardee)
        VALUES (:notice_id, :sol_number, :title, :agency, :notice_type, :posted_date,
                :last_seen_date, :is_win, :award_date, :contract_officer, :awardee)
        """,
        defaults,
    )


# ---------------------------------------------------------------------------
# _parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_plain_iso_date(self) -> None:
        assert tta._parse_date("2024-03-15") == date(2024, 3, 15)

    def test_datetime_with_offset(self) -> None:
        result = tta._parse_date("2024-03-15 12:40:56.966-04")
        assert result == date(2024, 3, 15)

    def test_iso_datetime_tz(self) -> None:
        result = tta._parse_date("2024-04-19T12:00:00+00:00")
        assert result == date(2024, 4, 19)

    def test_none_returns_none(self) -> None:
        assert tta._parse_date(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert tta._parse_date("") is None

    def test_garbage_returns_none(self) -> None:
        assert tta._parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# _days_between
# ---------------------------------------------------------------------------

class TestDaysBetween:
    def test_same_day_returns_zero(self) -> None:
        d = date(2024, 3, 15)
        assert tta._days_between(d, d) == 0

    def test_positive_gap(self) -> None:
        start = date(2024, 1, 1)
        end = date(2024, 4, 10)
        assert tta._days_between(start, end) == 100

    def test_award_before_solicitation_returns_none(self) -> None:
        start = date(2024, 4, 10)
        end = date(2024, 1, 1)
        assert tta._days_between(start, end) is None

    def test_none_start_returns_none(self) -> None:
        assert tta._days_between(None, date(2024, 3, 15)) is None

    def test_none_end_returns_none(self) -> None:
        assert tta._days_between(date(2024, 3, 15), None) is None


# ---------------------------------------------------------------------------
# compute_cycle_times
# ---------------------------------------------------------------------------

class TestComputeCycleTimes:
    def test_matched_pair_returns_days(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-A", notice_type="Solicitation",
                posted_date="2024-01-01")
        _insert(conn, notice_id="AWD1", sol_number="SOL-A", notice_type="Award Notice",
                award_date="2024-04-10", is_win=1)
        result = tta.compute_cycle_times(conn)
        assert len(result) == 1
        assert result[0]["days_to_award"] == 100
        assert result[0]["sol_number"] == "SOL-A"

    def test_no_matching_solicitation_excluded(self) -> None:
        conn = _make_db()
        # Award Notice with sol_number that has no solicitation in DB
        _insert(conn, notice_id="AWD1", sol_number="SOL-Z", notice_type="Award Notice",
                award_date="2024-04-10", is_win=1)
        result = tta.compute_cycle_times(conn)
        assert result == []

    def test_award_without_award_date_excluded(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-B", notice_type="Solicitation",
                posted_date="2024-01-01")
        _insert(conn, notice_id="AWD1", sol_number="SOL-B", notice_type="Award Notice",
                award_date=None, is_win=1)
        result = tta.compute_cycle_times(conn)
        assert result == []

    def test_award_before_solicitation_excluded(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-C", notice_type="Solicitation",
                posted_date="2024-06-01")
        _insert(conn, notice_id="AWD1", sol_number="SOL-C", notice_type="Award Notice",
                award_date="2024-01-01", is_win=1)
        result = tta.compute_cycle_times(conn)
        assert result == []

    def test_combined_synopsis_matched(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-D",
                notice_type="Combined Synopsis/Solicitation",
                posted_date="2024-02-01")
        _insert(conn, notice_id="AWD1", sol_number="SOL-D", notice_type="Award Notice",
                award_date="2024-03-02", is_win=1)
        result = tta.compute_cycle_times(conn)
        assert len(result) == 1
        assert result[0]["days_to_award"] == 30

    def test_same_day_award_returns_zero_days(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-E", notice_type="Solicitation",
                posted_date="2024-03-15")
        _insert(conn, notice_id="AWD1", sol_number="SOL-E", notice_type="Award Notice",
                award_date="2024-03-15", is_win=1)
        result = tta.compute_cycle_times(conn)
        assert len(result) == 1
        assert result[0]["days_to_award"] == 0

    def test_multiple_awards_all_returned(self) -> None:
        conn = _make_db()
        for i, (sol, awd, days) in enumerate(
            [("SOL-1", "2024-02-01", 31), ("SOL-2", "2024-03-01", 60)]
        ):
            _insert(conn, notice_id=f"SOL{i}", sol_number=sol,
                    notice_type="Solicitation", posted_date="2024-01-01")
            _insert(conn, notice_id=f"AWD{i}", sol_number=sol,
                    notice_type="Award Notice", award_date=awd, is_win=1)
        result = tta.compute_cycle_times(conn)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# aggregate_by_officer
# ---------------------------------------------------------------------------

class TestAggregateByOfficer:
    def _ct(self, officer: str, days: int, agency: str = "Agency A") -> dict:
        return {
            "contract_officer": officer,
            "days_to_award": days,
            "agency": agency,
        }

    def test_basic_stats(self) -> None:
        cts = [self._ct("Alice", 10), self._ct("Alice", 30)]
        result = tta.aggregate_by_officer(cts)
        assert len(result) == 1
        alice = result[0]
        assert alice["name"] == "Alice"
        assert alice["avg_days"] == 20.0
        assert alice["median_days"] == 20.0
        assert alice["fastest_award"] == 10
        assert alice["slowest_award"] == 30
        assert alice["awarded"] == 2

    def test_min_awards_filter(self) -> None:
        cts = [self._ct("Alice", 10), self._ct("Bob", 20), self._ct("Bob", 30)]
        result = tta.aggregate_by_officer(cts, min_awards=2)
        names = [r["name"] for r in result]
        assert "Bob" in names
        assert "Alice" not in names

    def test_sorted_by_avg_days_ascending(self) -> None:
        cts = [self._ct("Slow", 90), self._ct("Fast", 5)]
        result = tta.aggregate_by_officer(cts)
        assert result[0]["name"] == "Fast"
        assert result[1]["name"] == "Slow"

    def test_agencies_deduplicated(self) -> None:
        cts = [
            self._ct("Alice", 10, "Agency A"),
            self._ct("Alice", 20, "Agency A"),
            self._ct("Alice", 30, "Agency B"),
        ]
        result = tta.aggregate_by_officer(cts)
        assert sorted(result[0]["agencies"]) == ["Agency A", "Agency B"]

    def test_unknown_officer_grouped(self) -> None:
        cts = [{"contract_officer": None, "days_to_award": 15, "agency": "X"}]
        result = tta.aggregate_by_officer(cts)
        assert result[0]["name"] == "Unknown"


# ---------------------------------------------------------------------------
# aggregate_by_agency
# ---------------------------------------------------------------------------

class TestAggregateByAgency:
    def _ct(self, agency: str, days: int) -> dict:
        return {"agency": agency, "days_to_award": days, "contract_officer": None}

    def _abandoned(self, agency: str, days_since: int = 100) -> dict:
        return {
            "notice_id": "N001",
            "title": "T",
            "agency": agency,
            "officer": None,
            "posted_date": "2024-01-01",
            "last_seen_date": "2024-01-01",
            "days_since_last_seen": days_since,
        }

    def test_basic_metrics(self) -> None:
        cts = [self._ct("DOD", 30), self._ct("DOD", 60)]
        result = tta.aggregate_by_agency(cts, [])
        dod = next(r for r in result if r["agency"] == "DOD")
        assert dod["awarded"] == 2
        assert dod["avg_days"] == 45.0
        assert dod["never_awarded_count"] == 0

    def test_abandoned_counted_per_agency(self) -> None:
        cts = [self._ct("DOD", 30)]
        abandoned = [self._abandoned("NASA"), self._abandoned("NASA")]
        result = tta.aggregate_by_agency(cts, abandoned)
        nasa = next(r for r in result if r["agency"] == "NASA")
        assert nasa["never_awarded_count"] == 2
        assert nasa["avg_days"] is None

    def test_agency_with_only_abandoned_included(self) -> None:
        result = tta.aggregate_by_agency([], [self._abandoned("ALONE")])
        agencies = [r["agency"] for r in result]
        assert "ALONE" in agencies

    def test_agencies_with_timing_sorted_first(self) -> None:
        cts = [self._ct("Fast", 10), self._ct("Slow", 200)]
        abandoned = [self._abandoned("NoData")]
        result = tta.aggregate_by_agency(cts, abandoned)
        # Agencies with data come first
        assert result[-1]["agency"] == "NoData"


# ---------------------------------------------------------------------------
# find_abandoned
# ---------------------------------------------------------------------------

class TestFindAbandoned:
    def test_stale_solicitation_flagged(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-A",
                notice_type="Solicitation",
                posted_date="2023-01-01",
                last_seen_date="2023-01-01")
        as_of = date(2024, 1, 1)  # 365 days later (2023 is not a leap year)
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert len(result) == 1
        assert result[0]["notice_id"] == "SOL1"
        assert result[0]["days_since_last_seen"] == 365

    def test_recently_seen_not_flagged(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-B",
                notice_type="Solicitation",
                posted_date="2024-01-01",
                last_seen_date="2024-01-01")
        as_of = date(2024, 1, 30)  # 29 days later
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert result == []

    def test_awarded_solicitation_not_flagged(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-C",
                notice_type="Solicitation",
                posted_date="2023-01-01",
                last_seen_date="2023-01-01")
        _insert(conn, notice_id="AWD1", sol_number="SOL-C",
                notice_type="Award Notice", award_date="2023-06-01", is_win=1)
        as_of = date(2024, 1, 1)
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert result == []

    def test_combined_synopsis_flagged(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-D",
                notice_type="Combined Synopsis/Solicitation",
                posted_date="2023-01-01",
                last_seen_date="2023-01-01")
        as_of = date(2024, 6, 1)
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert len(result) == 1

    def test_presolicitation_flagged(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-E",
                notice_type="Presolicitation",
                posted_date="2023-01-01",
                last_seen_date="2023-01-01")
        as_of = date(2024, 6, 1)
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert len(result) == 1

    def test_sorted_by_days_since_last_seen_descending(self) -> None:
        conn = _make_db()
        _insert(conn, notice_id="SOL1", sol_number="SOL-F1",
                notice_type="Solicitation",
                posted_date="2022-01-01",
                last_seen_date="2022-01-01")
        _insert(conn, notice_id="SOL2", sol_number="SOL-F2",
                notice_type="Solicitation",
                posted_date="2023-01-01",
                last_seen_date="2023-01-01")
        as_of = date(2024, 6, 1)
        result = tta.find_abandoned(conn, stale_days=90, as_of=as_of)
        assert result[0]["days_since_last_seen"] >= result[1]["days_since_last_seen"]


# ---------------------------------------------------------------------------
# build_output (integration)
# ---------------------------------------------------------------------------

class TestBuildOutput:
    def test_empty_db_returns_valid_structure(self) -> None:
        conn = _make_db()
        as_of = date(2024, 6, 1)
        output = tta.build_output(conn, stale_days=90, as_of=as_of)
        assert "generated_date" in output
        assert "summary" in output
        assert "by_officer" in output
        assert "by_agency" in output
        assert "abandoned_opportunities" in output
        assert output["summary"]["total_awards_with_timing"] == 0
        assert output["summary"]["total_abandoned"] == 0

    def test_full_lifecycle(self) -> None:
        conn = _make_db()
        # Matched award
        _insert(conn, notice_id="SOL1", sol_number="SOL-A",
                notice_type="Solicitation", posted_date="2024-01-01",
                last_seen_date="2024-06-01", contract_officer="Alice")
        _insert(conn, notice_id="AWD1", sol_number="SOL-A",
                notice_type="Award Notice", award_date="2024-04-10",
                is_win=1, contract_officer="Alice")
        # Abandoned solicitation
        _insert(conn, notice_id="SOL2", sol_number="SOL-B",
                notice_type="Solicitation", posted_date="2022-01-01",
                last_seen_date="2022-01-01")

        as_of = date(2024, 6, 1)
        output = tta.build_output(conn, stale_days=90, as_of=as_of)

        assert output["summary"]["total_awards_with_timing"] == 1
        assert output["summary"]["total_abandoned"] == 1
        assert len(output["by_officer"]) == 1
        assert output["by_officer"][0]["name"] == "Alice"
        assert len(output["abandoned_opportunities"]) == 1

    def test_generated_date_matches_as_of(self) -> None:
        conn = _make_db()
        as_of = date(2025, 3, 20)
        output = tta.build_output(conn, as_of=as_of)
        assert output["generated_date"] == "2025-03-20"

    def test_stale_days_threshold_in_output(self) -> None:
        conn = _make_db()
        output = tta.build_output(conn, stale_days=180)
        assert output["stale_days_threshold"] == 180


# ---------------------------------------------------------------------------
# main() CLI (smoke test)
# ---------------------------------------------------------------------------

class TestMainCLI:
    def test_missing_db_exits_gracefully(self, tmp_path: Path, capsys) -> None:
        import sys
        nonexistent = tmp_path / "no.sqlite"
        output = tmp_path / "out.json"
        sys.argv = ["time_to_award.py", "--db", str(nonexistent), "--output", str(output)]
        tta.main()
        captured = capsys.readouterr()
        assert "not found" in captured.out.lower() or "not found" in captured.err.lower()
        assert not output.exists()

    def test_output_written(self, tmp_path: Path) -> None:
        import sys
        db_path = tmp_path / "test.sqlite"
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE opportunities (
                notice_id TEXT PRIMARY KEY,
                sol_number TEXT,
                title TEXT,
                agency TEXT,
                notice_type TEXT,
                posted_date TEXT,
                last_seen_date TEXT NOT NULL DEFAULT '',
                is_win INTEGER NOT NULL DEFAULT 0,
                award_date TEXT,
                contract_officer TEXT,
                awardee TEXT
            )
            """
        )
        conn.commit()
        conn.close()

        output_path = tmp_path / "result.json"
        sys.argv = [
            "time_to_award.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]
        tta.main()
        assert output_path.exists()
        data = json.loads(output_path.read_text())
        assert data["summary"]["total_awards_with_timing"] == 0
