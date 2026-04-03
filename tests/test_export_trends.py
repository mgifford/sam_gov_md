"""Tests for export_trends.py."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import export_trends as et
import persist_to_sqlite as pst


def _build_db(path: Path, records: list[dict] | None = None, date: str = "2024-03-15") -> None:
    """Create a minimal opportunities SQLite database for testing."""
    conn = sqlite3.connect(path)
    pst.init_db(conn)
    default_records = [
        {
            "NoticeId": "TREND001",
            "Sol#": "W912-001",
            "Title": "Opportunity 1",
            "Department/Ind.Agency": "DEPT OF DEFENSE",
            "Type": "Solicitation",
            "PostedDate": "2024-01-01",
            "ResponseDeadLine": "2024-02-01",
            "NaicsCode": "541511",
            "Link": "https://sam.gov/opp/TREND001",
            "AwardNumber": "",
            "Awardee": "",
            "Award$": "",
            "Description": "Test",
            "matches": "",
        },
        {
            "NoticeId": "TREND002",
            "Sol#": "W912-002",
            "Title": "Award 1",
            "Department/Ind.Agency": "DEPT OF STATE",
            "Type": "Award Notice",
            "PostedDate": "2024-02-01",
            "ResponseDeadLine": "",
            "NaicsCode": "541512",
            "Link": "https://sam.gov/opp/TREND002",
            "AwardNumber": "AWARD-001",
            "Awardee": "Acme Corp",
            "Award$": "500000",
            "Description": "Award",
            "matches": "",
        },
    ]
    for row in (records or default_records):
        pst.upsert_record(conn, row, date)
    conn.commit()
    conn.close()


class TestExportTrends:
    def test_creates_trends_json(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_dir = tmp_path / "docs" / "data"

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        trends_file = output_dir / "trends.json"
        assert trends_file.exists()

    def test_output_structure(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_dir = tmp_path / "docs" / "data"

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        trends = json.loads((output_dir / "trends.json").read_text(encoding="utf-8"))
        assert "timeline" in trends
        assert "agencies" in trends
        assert "top_agencies" in trends
        assert "daily_totals" in trends

    def test_agencies_by_name(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_dir = tmp_path / "docs" / "data"

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        trends = json.loads((output_dir / "trends.json").read_text(encoding="utf-8"))
        agencies = trends["agencies"]
        assert "DEPT OF DEFENSE" in agencies
        assert "DEPT OF STATE" in agencies

    def test_timeline_sorted(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_dir = tmp_path / "docs" / "data"

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        trends = json.loads((output_dir / "trends.json").read_text(encoding="utf-8"))
        timeline = trends["timeline"]
        assert timeline == sorted(timeline)

    def test_missing_db_exits_gracefully(self, tmp_path: Path, capsys) -> None:
        output_dir = tmp_path / "docs" / "data"
        output_dir.mkdir(parents=True)

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(tmp_path / "nonexistent.sqlite"),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        captured = capsys.readouterr()
        assert "not found" in captured.out.lower()

    def test_daily_totals_contain_date_and_counts(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_dir = tmp_path / "docs" / "data"

        with patch("sys.argv", [
            "export_trends.py",
            "--db", str(db_path),
            "--output-dir", str(output_dir),
        ]):
            et.main()

        trends = json.loads((output_dir / "trends.json").read_text(encoding="utf-8"))
        assert len(trends["daily_totals"]) > 0
        entry = trends["daily_totals"][0]
        assert "date" in entry
        assert "total" in entry
        assert "opportunities" in entry
        assert "wins" in entry
