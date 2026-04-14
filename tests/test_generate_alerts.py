"""Tests for generate_alerts.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import generate_alerts as ga


# ---------------------------------------------------------------------------
# score_record
# ---------------------------------------------------------------------------

class TestScoreRecord:
    def _record(self, matches: list[dict]) -> dict:
        return {"matches": matches}

    def test_total_hits_summed(self) -> None:
        record = self._record([
            {"term": "web", "count": 3},
            {"term": "api", "count": 5},
        ])
        total, include = ga.score_record(record, min_hits=1)
        assert total == 8

    def test_qualifies_with_focus_term_and_enough_hits(self) -> None:
        record = self._record([{"term": "web", "count": 10}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_disqualified_below_min_hits(self) -> None:
        record = self._record([{"term": "web", "count": 3}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is False

    def test_disqualified_no_focus_term(self) -> None:
        # "platform" is not a focus term in generate_alerts.FOCUS_TERMS
        record = self._record([{"term": "platform", "count": 20}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is False

    def test_qualifies_with_digital_naics_signal(self) -> None:
        record = {
            "matches": [{"term": "platform", "count": 20}],
            "NaicsCode": "541512",
        }
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_qualifies_with_digital_psc_signal(self) -> None:
        record = {
            "matches": [{"term": "platform", "count": 20}],
            "ClassificationCode": "D399",
        }
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_non_digital_naics_without_focus_term_still_disqualified(self) -> None:
        record = {
            "matches": [{"term": "platform", "count": 20}],
            "NaicsCode": "236220",
        }
        _, include = ga.score_record(record, min_hits=8)
        assert include is False

    def test_empty_matches_returns_zero_not_included(self) -> None:
        total, include = ga.score_record({"matches": []}, min_hits=8)
        assert total == 0
        assert include is False

    def test_missing_matches_key(self) -> None:
        total, include = ga.score_record({}, min_hits=8)
        assert total == 0
        assert include is False

    def test_focus_term_case_insensitive(self) -> None:
        # FOCUS_TERMS contains lowercase versions; term strings are lowercased.
        record = self._record([{"term": "WEB", "count": 10}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_all_focus_terms_qualify(self) -> None:
        for term in ga.FOCUS_TERMS:
            record = self._record([{"term": term, "count": 10}])
            _, include = ga.score_record(record, min_hits=8)
            assert include is True, f"Focus term '{term}' should qualify"

    def test_focus_term_lookup_is_case_insensitive(self) -> None:
        # score_record lowercases matched terms; FOCUS_TERMS are now all
        # lowercase, so "uswds", "user experience", etc. all match.
        for term in ("uswds", "user experience", "content management system"):
            record = self._record([{"term": term, "count": 20}])
            _, include = ga.score_record(record, min_hits=8)
            assert include is True, f"Focus term '{term}' should qualify"

    def test_acr_focus_term_qualifies(self) -> None:
        record = self._record([{"term": "ACR", "count": 12}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_acr_focus_term_lowercase_qualifies(self) -> None:
        record = self._record([{"term": "acr", "count": 12}])
        _, include = ga.score_record(record, min_hits=8)
        assert include is True

    def test_zero_min_hits_always_passes_threshold(self) -> None:
        record = self._record([{"term": "api", "count": 1}])
        _, include = ga.score_record(record, min_hits=0)
        assert include is True

    def test_count_field_coerced_from_string(self) -> None:
        # count may come in as a string from JSON; int() must handle it
        record = self._record([{"term": "api", "count": "5"}])
        total, _ = ga.score_record(record, min_hits=1)
        assert total == 5


# ---------------------------------------------------------------------------
# main() integration — writing output files
# ---------------------------------------------------------------------------

class TestMain:
    def _write_summary(self, tmp_path: Path, records: list[dict]) -> Path:
        summary = {
            "requested_date": "2024-03-15",
            "effective_date": "2024-03-15",
            "records_total": len(records),
            "top_matching_records": records,
        }
        p = tmp_path / "summary.json"
        p.write_text(json.dumps(summary), encoding="utf-8")
        return p

    def _run_main(self, tmp_path: Path, records: list[dict], min_hits: int = 8) -> None:
        summary_path = self._write_summary(tmp_path, records)
        import sys
        argv_backup = sys.argv[:]
        sys.argv = [
            "generate_alerts.py",
            "--summary", str(summary_path),
            "--output-json", str(tmp_path / "matches.json"),
            "--output-md", str(tmp_path / "alert.md"),
            "--output-meta", str(tmp_path / "meta.json"),
            "--min-hits", str(min_hits),
        ]
        try:
            ga.main()
        finally:
            sys.argv = argv_backup

    def test_no_matches_writes_empty_result(self, tmp_path: Path) -> None:
        self._run_main(tmp_path, [])
        matches = json.loads((tmp_path / "matches.json").read_text())
        assert matches["high_value_count"] == 0

    def test_qualifying_record_appears_in_output(self, tmp_path: Path) -> None:
        record = {
            "NoticeId": "N001",
            "Title": "Web Portal Modernization",
            "Agency": "DoD",
            "Type": "Solicitation",
            "PostedDate": "2024-03-15",
            "matches": [{"term": "web", "count": 10}],
        }
        self._run_main(tmp_path, [record], min_hits=8)
        matches = json.loads((tmp_path / "matches.json").read_text())
        assert matches["high_value_count"] == 1

    def test_below_threshold_record_excluded(self, tmp_path: Path) -> None:
        record = {
            "NoticeId": "N002",
            "Title": "Minor Task",
            "Agency": "GSA",
            "matches": [{"term": "web", "count": 2}],
        }
        self._run_main(tmp_path, [record], min_hits=8)
        matches = json.loads((tmp_path / "matches.json").read_text())
        assert matches["high_value_count"] == 0

    def test_markdown_written(self, tmp_path: Path) -> None:
        self._run_main(tmp_path, [])
        assert (tmp_path / "alert.md").exists()

    def test_markdown_contains_header(self, tmp_path: Path) -> None:
        self._run_main(tmp_path, [])
        content = (tmp_path / "alert.md").read_text()
        assert "# High-value SAM.gov Matches" in content

    def test_meta_file_written(self, tmp_path: Path) -> None:
        self._run_main(tmp_path, [])
        assert (tmp_path / "meta.json").exists()

    def test_results_sorted_by_total_hits_desc(self, tmp_path: Path) -> None:
        records = [
            {
                "NoticeId": "N001",
                "Title": "Low Score",
                "matches": [{"term": "web", "count": 8}],
            },
            {
                "NoticeId": "N002",
                "Title": "High Score",
                "matches": [{"term": "api", "count": 20}],
            },
        ]
        self._run_main(tmp_path, records, min_hits=8)
        matches = json.loads((tmp_path / "matches.json").read_text())
        if matches["high_value_count"] >= 2:
            assert matches["matches"][0]["total_hits"] >= matches["matches"][1]["total_hits"]
