"""Tests for export_all_opportunities.py."""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

import export_all_opportunities as eao
import persist_to_sqlite as pst


def _build_db(path: Path) -> None:
    """Create a minimal opportunities SQLite database for testing."""
    conn = sqlite3.connect(path)
    pst.init_db(conn)
    rows = [
        {
            "NoticeId": "OPP001",
            "Sol#": "W912-001",
            "Title": "Test Opportunity 1",
            "Department/Ind.Agency": "DEPT OF DEFENSE",
            "Type": "Solicitation",
            "PostedDate": "2024-03-01",
            "ResponseDeadLine": "2024-04-01",
            "NaicsCode": "541511",
            "Link": "https://sam.gov/opp/OPP001",
            "AwardNumber": "",
            "Awardee": "",
            "Award$": "",
            "Description": "First opportunity description",
            "matches": [{"term": "web", "count": 3}],
        },
        {
            "NoticeId": "OPP002",
            "Sol#": "W912-002",
            "Title": "Test Award 1",
            "Department/Ind.Agency": "DEPT OF STATE",
            "Type": "Award Notice",
            "PostedDate": "2024-03-02",
            "ResponseDeadLine": "",
            "NaicsCode": "541512",
            "Link": "https://sam.gov/opp/OPP002",
            "AwardNumber": "AWARD-001",
            "Awardee": "Acme Corp",
            "Award$": "500000",
            "Description": "Award description",
            "matches": "",
        },
    ]
    for row in rows:
        pst.upsert_record(conn, row, "2024-03-15")
    conn.commit()
    conn.close()


class TestExportAllOpportunities:
    def test_exports_records_to_json(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]):
            eao.main()

        assert output_path.exists()
        records = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(records) == 2

    def test_output_contains_expected_fields(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]):
            eao.main()

        records = json.loads(output_path.read_text(encoding="utf-8"))
        rec = next(r for r in records if r.get("NoticeId") == "OPP001")
        assert rec["Title"] == "Test Opportunity 1"
        assert rec["Agency"] == "DEPT OF DEFENSE"
        assert isinstance(rec["is_win"], bool)

    def test_matches_parsed_as_list(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]):
            eao.main()

        records = json.loads(output_path.read_text(encoding="utf-8"))
        rec = next(r for r in records if r.get("NoticeId") == "OPP001")
        assert isinstance(rec["matches"], list)
        assert rec["matches"][0]["term"] == "web"

    def test_empty_matches_returns_empty_list(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]):
            eao.main()

        records = json.loads(output_path.read_text(encoding="utf-8"))
        rec = next(r for r in records if r.get("NoticeId") == "OPP002")
        assert rec["matches"] == []

    def test_limit_option(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
            "--limit", "1",
        ]):
            eao.main()

        records = json.loads(output_path.read_text(encoding="utf-8"))
        assert len(records) == 1

    def test_missing_db_writes_empty_list(self, tmp_path: Path) -> None:
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(tmp_path / "nonexistent.sqlite"),
            "--output", str(output_path),
        ]):
            eao.main()

        assert output_path.exists()
        records = json.loads(output_path.read_text(encoding="utf-8"))
        assert records == []

    def test_has_pdf_content_false_by_default(self, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunities.sqlite"
        _build_db(db_path)
        output_path = tmp_path / "all_opportunities.json"

        with patch("sys.argv", [
            "export_all_opportunities.py",
            "--db", str(db_path),
            "--output", str(output_path),
        ]):
            eao.main()

        records = json.loads(output_path.read_text(encoding="utf-8"))
        for rec in records:
            assert rec["has_pdf_content"] is False
