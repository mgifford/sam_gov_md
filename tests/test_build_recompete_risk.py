"""Tests for build_recompete_risk.py."""

from __future__ import annotations

import json
from datetime import date

import build_recompete_risk as br


def test_quarter_from_date() -> None:
    """Quarter mapping should follow calendar quarters."""
    assert br.quarter_from_date(date(2026, 1, 15)) == "Q1"
    assert br.quarter_from_date(date(2026, 4, 1)) == "Q2"
    assert br.quarter_from_date(date(2026, 7, 1)) == "Q3"
    assert br.quarter_from_date(date(2026, 10, 1)) == "Q4"


def test_set_aside_detection() -> None:
    """Small-business set-aside detection should be case-insensitive."""
    assert br.is_small_business_set_aside("Total Small Business Set-Aside") is True
    assert br.is_small_business_set_aside("SMALL BUSINESS SET ASIDE") is True
    assert br.is_small_business_set_aside("Full and Open Competition") is False
    assert br.is_small_business_set_aside(None) is False


def test_parse_date_variants() -> None:
    """Date parser should support date-only and datetime formats."""
    assert br.parse_date("2027-09-30") == date(2027, 9, 30)
    assert br.parse_date("2027-09-30 10:30:00") == date(2027, 9, 30)
    assert br.parse_date("not-a-date") is None


def test_load_companies_string_list(tmp_path) -> None:
    """String-based list should load as Company entries."""
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(["A", "B", "A"]), encoding="utf-8")

    companies = br.load_companies(path)
    assert [c.name for c in companies] == ["A", "B"]
    assert companies[0].uei is None


def test_load_companies_object_list(tmp_path) -> None:
    """Object-based list should preserve UEI when provided."""
    path = tmp_path / "companies.json"
    path.write_text(
        json.dumps(
            [
                {"name": "Example", "uei": "ABC123"},
                {"name": "No UEI", "uei": ""},
            ]
        ),
        encoding="utf-8",
    )

    companies = br.load_companies(path)
    assert companies[0].name == "Example"
    assert companies[0].uei == "ABC123"
    assert companies[1].uei is None


def test_load_companies_tracking_schema(tmp_path) -> None:
    """Tracking schema using company_name should load without conversion."""
    path = tmp_path / "companies_tracking.json"
    path.write_text(
        json.dumps(
            [
                {
                    "company_name": "Lockheed Martin",
                    "sector": "Defense & Aerospace",
                    "primary_focus": "Fighter Jets, Missiles, Space Systems",
                },
                {
                    "company_name": "Microsoft",
                    "sector": "Technology",
                    "primary_focus": "Cloud Services (Azure), Software",
                },
            ]
        ),
        encoding="utf-8",
    )

    companies = br.load_companies(path)
    assert [c.name for c in companies] == ["Lockheed Martin", "Microsoft"]


def test_build_recompete_rows_shape() -> None:
    """ParaCharts rows should follow expected output schema."""
    awards = [
        {
            "Award ID": "A-1",
            "Recipient Name": "Company",
            "Recipient UEI": "UEI123",
            "Awarding Agency": "Department of Veterans Affairs",
            "Award Amount": 123456.0,
            "Description": "Human-centered design and software development support",
            "Type Set Aside": "Total Small Business Set-Aside",
            "Period of Performance End Date": "2027-03-31",
            "Period of Performance Current End Date": "2027-03-31",
        }
    ]

    para_rows, detail_rows = br.build_recompete_rows(awards)
    assert len(para_rows) == 1
    assert len(detail_rows) == 1

    row = para_rows[0]
    assert set(row.keys()) == {
        "agency",
        "value",
        "expiry_quarter",
        "set_aside_status",
        "benchmark_diff",
    }
    assert row["expiry_quarter"] == "Q1"


def test_resolve_companies_file_uses_cohort() -> None:
    """Cohort preset should resolve to known config file paths."""
    path = br.resolve_companies_file("ai", "config/company_lists/dsc.json")
    assert str(path).endswith("config/company_lists/ai_vendors_federal.json")


def test_resolve_companies_file_uses_explicit_file() -> None:
    """Explicit file should be used when no cohort is supplied."""
    path = br.resolve_companies_file(None, "config/company_lists/example_companies.json")
    assert str(path).endswith("config/company_lists/example_companies.json")


def test_build_paracharts_specs_structure() -> None:
    """ParaCharts spec generator should emit expected top-level keys."""
    rows = [
        {
            "agency": "Department of Veterans Affairs",
            "value": 1200000,
            "expiry_quarter": "Q2",
            "set_aside_status": "Total Small Business Set-Aside",
            "benchmark_diff": 0,
        },
        {
            "agency": "Department of Veterans Affairs",
            "value": 300000,
            "expiry_quarter": "Q4",
            "set_aside_status": "Full and Open Competition",
            "benchmark_diff": 18,
        },
    ]

    specs = br.build_paracharts_specs(rows)
    assert specs["version"] == "1.0"
    assert specs["row_count"] == 2
    assert len(specs["manifests"]) == 4
    assert specs["manifests"][0]["manifest"]["type"] == "bar"


def test_extract_hourly_rate_from_text() -> None:
    """Hourly rate parser should find common dollar per hour patterns."""
    assert br._extract_hourly_rate_from_text("Labor at $175/hr for senior engineer") == 175.0
    assert br._extract_hourly_rate_from_text("pricing is 142 per hour") is None


def test_rate_benchmark_resolver_fallback() -> None:
    """Fallback benchmark mode should return a non-zero proxy diff."""
    resolver = br.RateBenchmarkResolver(mode="fallback", bls_burden_multiplier=2.0)
    diff, meta = resolver.resolve("Software Engineer", None)
    assert diff > 0
    assert meta["source_mode"] == "fallback"
