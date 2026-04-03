"""Tests for extract_contract_officers.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import extract_contract_officers as eco


# ---------------------------------------------------------------------------
# extract_officers
# ---------------------------------------------------------------------------

class TestExtractOfficers:
    def _records(self, tmp_path: Path, records: list[dict]) -> Path:
        p = tmp_path / "records.json"
        p.write_text(json.dumps(records), encoding="utf-8")
        return p

    def _summary(self, tmp_path: Path, effective_date: str = "2024-03-15") -> Path:
        p = tmp_path / "summary.json"
        p.write_text(json.dumps({"effective_date": effective_date}), encoding="utf-8")
        return p

    def test_missing_records_file_exits_early(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(missing, summary, output)
        # Output should not be created
        assert not output.exists()

    def test_empty_records_creates_output(self, tmp_path: Path) -> None:
        records = self._records(tmp_path, [])
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["total_unique_officers"] == 0
        assert result["top_officers"] == []

    def test_primary_contact_counted(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT OF DEFENSE",
                "PrimaryContactFullname": "Alice Jones",
                "PrimaryContactEmail": "alice@defense.gov",
                "PrimaryContactPhone": "555-0001",
                "AwardNumber": "",
                "Award$": "0",
            }
        ]
        records = self._records(tmp_path, records_data)
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["total_unique_officers"] == 1
        officer = result["top_officers"][0]
        assert officer["name"] == "Alice Jones"
        assert officer["email"] == "alice@defense.gov"
        assert officer["opportunities"] == 1

    def test_secondary_contact_counted(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT OF STATE",
                "PrimaryContactFullname": "",
                "SecondaryContactFullname": "Bob Smith",
                "SecondaryContactEmail": "bob@state.gov",
                "SecondaryContactPhone": "555-0002",
                "AwardNumber": "",
                "Award$": "0",
            }
        ]
        records = self._records(tmp_path, records_data)
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["total_unique_officers"] == 1
        officer = result["top_officers"][0]
        assert officer["name"] == "Bob Smith"
        assert officer["secondary_role"] == 1

    def test_award_value_accumulated(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT OF DEFENSE",
                "PrimaryContactFullname": "Carol White",
                "PrimaryContactEmail": "carol@defense.gov",
                "PrimaryContactPhone": "",
                "AwardNumber": "W912-001",
                "Award$": "500000",
            },
            {
                "Department/Ind.Agency": "DEPT OF DEFENSE",
                "PrimaryContactFullname": "Carol White",
                "PrimaryContactEmail": "carol@defense.gov",
                "PrimaryContactPhone": "",
                "AwardNumber": "W912-002",
                "Award$": "250000",
            },
        ]
        records = self._records(tmp_path, records_data)
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        officer = result["top_officers"][0]
        assert officer["awards"] == 2
        assert officer["total_award_value"] == 750000

    def test_effective_date_from_summary(self, tmp_path: Path) -> None:
        records = self._records(tmp_path, [])
        summary = self._summary(tmp_path, "2024-06-01")
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["extraction_date"] == "2024-06-01"

    def test_officers_by_department_populated(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT A",
                "PrimaryContactFullname": "Officer One",
                "PrimaryContactEmail": "one@dept.gov",
                "PrimaryContactPhone": "",
                "AwardNumber": "",
                "Award$": "0",
            }
        ]
        records = self._records(tmp_path, records_data)
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert "DEPT A" in result["officers_by_department"]

    def test_missing_summary_sets_null_date(self, tmp_path: Path) -> None:
        records = self._records(tmp_path, [])
        missing_summary = tmp_path / "no_summary.json"
        output = tmp_path / "output.json"
        eco.extract_officers(records, missing_summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["extraction_date"] is None

    def test_invalid_award_value_handled(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT X",
                "PrimaryContactFullname": "Bad Value Officer",
                "PrimaryContactEmail": "",
                "PrimaryContactPhone": "",
                "AwardNumber": "W000-001",
                "Award$": "not-a-number",
            }
        ]
        records = self._records(tmp_path, records_data)
        summary = self._summary(tmp_path)
        output = tmp_path / "output.json"
        # Should not raise
        eco.extract_officers(records, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        officer = result["top_officers"][0]
        assert officer["total_award_value"] == 0
