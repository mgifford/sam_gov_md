"""Tests for department_forecasting.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import department_forecasting as df


# ---------------------------------------------------------------------------
# forecast_departments
# ---------------------------------------------------------------------------

class TestForecastDepartments:
    def _write(self, tmp_path: Path, name: str, data) -> Path:
        p = tmp_path / name
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def _departments(self, names: list[str]) -> list[dict]:
        return [
            {"department": d, "total": 5, "opportunities": 3, "wins": 2}
            for d in names
        ]

    def test_missing_records_exits_early(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT A"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-01-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(missing, dept, summary, output)
        assert not output.exists()

    def test_missing_departments_exits_early(self, tmp_path: Path) -> None:
        records = self._write(tmp_path, "records.json", [])
        missing = tmp_path / "no_dept.json"
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-01-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, missing, summary, output)
        assert not output.exists()

    def test_empty_records_produces_output(self, tmp_path: Path) -> None:
        records = self._write(tmp_path, "records.json", [])
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT A"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-02-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        assert output.exists()
        result = json.loads(output.read_text(encoding="utf-8"))
        assert "departments_by_opportunity_volume" in result
        assert "departments_by_award_value" in result

    def test_win_rate_calculated(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT A",
                "Title": "Opp 1",
                "NoticeId": "001",
                "PostedDate": "2024-01-01",
                "ResponseDeadLine": "",
                "Description": "",
                "AttachmentCount": 0,
                "matches": [],
                "Sol#": "",
                "AwardNumber": "AWARD-001",
                "Award$": "100000",
                "Awardee": "Acme Corp",
                "AwardDate": "2024-02-01",
            },
            {
                "Department/Ind.Agency": "DEPT A",
                "Title": "Opp 2",
                "NoticeId": "002",
                "PostedDate": "2024-01-02",
                "ResponseDeadLine": "",
                "Description": "",
                "AttachmentCount": 0,
                "matches": [],
                "Sol#": "",
                "AwardNumber": "",
                "Award$": "",
                "Awardee": "",
                "AwardDate": "",
            },
        ]
        records = self._write(tmp_path, "records.json", records_data)
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT A"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-03-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        dept_forecast = result["department_forecasts"]["DEPT A"]
        assert dept_forecast["win_rate_percent"] == 50.0

    def test_award_value_summed(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT B",
                "Title": "Award 1",
                "NoticeId": "B001",
                "PostedDate": "2024-01-01",
                "ResponseDeadLine": "",
                "Description": "",
                "AttachmentCount": 0,
                "matches": [],
                "Sol#": "",
                "AwardNumber": "B-AWARD-001",
                "Award$": "500000",
                "Awardee": "Corp One",
                "AwardDate": "2024-02-01",
            },
            {
                "Department/Ind.Agency": "DEPT B",
                "Title": "Award 2",
                "NoticeId": "B002",
                "PostedDate": "2024-01-02",
                "ResponseDeadLine": "",
                "Description": "",
                "AttachmentCount": 0,
                "matches": [],
                "Sol#": "",
                "AwardNumber": "B-AWARD-002",
                "Award$": "300000",
                "Awardee": "Corp Two",
                "AwardDate": "2024-02-15",
            },
        ]
        records = self._write(tmp_path, "records.json", records_data)
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT B"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-03-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        dept_forecast = result["department_forecasts"]["DEPT B"]
        assert dept_forecast["estimated_monthly_value"] == 800000

    def test_effective_date_from_summary(self, tmp_path: Path) -> None:
        records = self._write(tmp_path, "records.json", [])
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT X"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2025-01-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert result["forecast_date"] == "2025-01-01"

    def test_ranked_lists_in_output(self, tmp_path: Path) -> None:
        records = self._write(tmp_path, "records.json", [])
        depts = self._departments(["ALPHA", "BETA", "GAMMA"])
        dept = self._write(tmp_path, "dept.json", depts)
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-01-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        assert len(result["departments_by_opportunity_volume"]) == 3
        assert len(result["departments_by_award_value"]) == 3

    def test_top_awardees_deduped(self, tmp_path: Path) -> None:
        records_data = [
            {
                "Department/Ind.Agency": "DEPT C",
                "Title": f"Award {i}",
                "NoticeId": f"C{i:03d}",
                "PostedDate": "2024-01-01",
                "ResponseDeadLine": "",
                "Description": "",
                "AttachmentCount": 0,
                "matches": [],
                "Sol#": "",
                "AwardNumber": f"AWARD-{i:03d}",
                "Award$": "100000",
                "Awardee": "Same Corp",
                "AwardDate": "2024-02-01",
            }
            for i in range(3)
        ]
        records = self._write(tmp_path, "records.json", records_data)
        dept = self._write(tmp_path, "dept.json", self._departments(["DEPT C"]))
        summary = self._write(tmp_path, "summary.json", {"effective_date": "2024-03-01"})
        output = tmp_path / "output.json"
        df.forecast_departments(records, dept, summary, output)
        result = json.loads(output.read_text(encoding="utf-8"))
        awardees = result["department_forecasts"]["DEPT C"]["top_awardees"]
        # "Same Corp" should appear only once in the top awardees list
        names = [a["name"] for a in awardees]
        assert names.count("Same Corp") == 1
        assert awardees[0]["wins"] == 3
