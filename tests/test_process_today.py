"""Tests for process_today.py helper functions."""

from __future__ import annotations

import sys
import types
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# Bootstrap: provide a minimal stub for ollama_analyzer so that
# process_today can be imported without the real Ollama/requests dependency.
# ---------------------------------------------------------------------------
_ollama_stub = types.ModuleType("ollama_analyzer")
_ollama_stub.OllamaClient = MagicMock  # type: ignore[attr-defined]
_ollama_stub.GitHubModelsClient = MagicMock  # type: ignore[attr-defined]
_ollama_stub.analyze_record = MagicMock(return_value="")  # type: ignore[attr-defined]
sys.modules.setdefault("ollama_analyzer", _ollama_stub)

import process_today as pt  # noqa: E402


# ---------------------------------------------------------------------------
# normalize_date
# ---------------------------------------------------------------------------

class TestNormalizeDate:
    def test_iso_datetime_truncated(self) -> None:
        assert pt.normalize_date("2024-03-15T00:00:00") == "2024-03-15"

    def test_iso_date_unchanged(self) -> None:
        assert pt.normalize_date("2024-03-15") == "2024-03-15"

    def test_empty_string_returns_empty(self) -> None:
        assert pt.normalize_date("") == ""

    def test_none_returns_empty(self) -> None:
        assert pt.normalize_date(None) == ""  # type: ignore[arg-type]

    def test_long_string_truncated_to_10(self) -> None:
        assert pt.normalize_date("2024-12-31 extra data here") == "2024-12-31"

    def test_short_string_returned_as_is(self) -> None:
        # Less than 10 chars: returned as-is ([:10] on a short string)
        assert pt.normalize_date("2024") == "2024"


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    from datetime import date as _date

    def test_iso_format(self) -> None:
        from datetime import date
        assert pt.parse_date("2024-03-15") == date(2024, 3, 15)

    def test_us_slash_format(self) -> None:
        from datetime import date
        assert pt.parse_date("03/15/2024") == date(2024, 3, 15)

    def test_empty_returns_none(self) -> None:
        assert pt.parse_date("") is None

    def test_none_returns_none(self) -> None:
        assert pt.parse_date(None) is None  # type: ignore[arg-type]

    def test_invalid_format_returns_none(self) -> None:
        assert pt.parse_date("not-a-date") is None

    def test_whitespace_stripped(self) -> None:
        from datetime import date
        assert pt.parse_date("  2024-01-01  ") == date(2024, 1, 1)

    def test_datetime_string_truncated_and_parsed(self) -> None:
        from datetime import date
        # Only first 10 chars are used, so the time part is ignored.
        assert pt.parse_date("2024-06-15T12:00:00") == date(2024, 6, 15)


# ---------------------------------------------------------------------------
# _decode_csv_line
# ---------------------------------------------------------------------------

class TestDecodeCsvLine:
    def test_valid_utf8(self) -> None:
        assert pt._decode_csv_line(b"hello world") == "hello world"

    def test_utf8_with_unicode(self) -> None:
        assert pt._decode_csv_line("café".encode("utf-8")) == "café"

    def test_windows1252_fallback(self) -> None:
        # 0x93 / 0x94 are Windows-1252 left/right double quotes
        result = pt._decode_csv_line(b"\x93hello\x94")
        assert "hello" in result


# ---------------------------------------------------------------------------
# clean_description
# ---------------------------------------------------------------------------

class TestCleanDescription:
    def test_html_entities_unescaped(self) -> None:
        assert pt.clean_description("AT&amp;T") == "AT&T"
        assert pt.clean_description("&lt;b&gt;bold&lt;/b&gt;") == "<b>bold</b>"

    def test_numeric_html_entity(self) -> None:
        assert pt.clean_description("it&#x2019;s") == "it\u2019s"

    def test_numbered_section_gets_blank_line(self) -> None:
        text = "Introduction 1.0 Scope"
        result = pt.clean_description(text)
        assert "\n\n" in result

    def test_empty_string_returned_unchanged(self) -> None:
        assert pt.clean_description("") == ""

    def test_none_returned_as_none(self) -> None:
        assert pt.clean_description(None) is None  # type: ignore[arg-type]

    def test_plain_text_unchanged(self) -> None:
        text = "No special characters here."
        assert pt.clean_description(text) == text


# ---------------------------------------------------------------------------
# is_win
# ---------------------------------------------------------------------------

class TestIsWin:
    def test_award_type_is_win(self) -> None:
        assert pt.is_win({"Type": "Award Notice"}) is True

    def test_award_case_insensitive(self) -> None:
        assert pt.is_win({"Type": "award notice"}) is True

    def test_non_award_type(self) -> None:
        assert pt.is_win({"Type": "Presolicitation"}) is False

    def test_missing_type_key(self) -> None:
        assert pt.is_win({}) is False


# ---------------------------------------------------------------------------
# extract_attachments
# ---------------------------------------------------------------------------

class TestExtractAttachments:
    def test_no_attachments(self) -> None:
        result = pt.extract_attachments("No attachments here.")
        assert result == {"count": 0, "attachments": []}

    def test_none_returns_empty(self) -> None:
        result = pt.extract_attachments(None)  # type: ignore[arg-type]
        assert result == {"count": 0, "attachments": []}

    def test_empty_string(self) -> None:
        result = pt.extract_attachments("")
        assert result == {"count": 0, "attachments": []}

    def test_attachment_pattern_detected(self) -> None:
        desc = "Attachment 1: Statement of Work.pdf\nAttachment 2: Price Schedule.xlsx"
        result = pt.extract_attachments(desc)
        assert result["count"] >= 1

    def test_exhibit_pattern_detected(self) -> None:
        desc = "Exhibit A: Performance Work Statement"
        result = pt.extract_attachments(desc)
        assert result["count"] >= 1

    def test_att_file_pattern_detected(self) -> None:
        desc = "Att 1_FAR 52.204-24 Nov 2021.pdf"
        result = pt.extract_attachments(desc)
        assert result["count"] >= 1

    def test_no_duplicate_attachments(self) -> None:
        desc = "Attachment 1: SOW.pdf"
        result = pt.extract_attachments(desc)
        names = result["attachments"]
        assert len(names) == len(set(names))


# ---------------------------------------------------------------------------
# load_terms
# ---------------------------------------------------------------------------

class TestLoadTerms:
    def test_loads_terms_from_real_config(self) -> None:
        config_path = Path(__file__).parent.parent / "config" / "terms.yml"
        terms = pt.load_terms(config_path)
        assert len(terms) > 0
        assert all(isinstance(t, pt.TermDef) for t in terms)

    def test_term_has_name_and_patterns(self) -> None:
        config_path = Path(__file__).parent.parent / "config" / "terms.yml"
        terms = pt.load_terms(config_path)
        for term in terms:
            assert term.name, "Every term must have a non-empty name"
            assert isinstance(term.patterns, list)

    def test_custom_yaml(self, tmp_path: Path) -> None:
        yaml_content = (
            "terms:\n"
            "  - name: testterm\n"
            "    category: test\n"
            "    patterns:\n"
            "      - '\\btestterm\\b'\n"
        )
        cfg = tmp_path / "terms.yml"
        cfg.write_text(yaml_content, encoding="utf-8")
        terms = pt.load_terms(cfg)
        assert len(terms) == 1
        assert terms[0].name == "testterm"
        assert terms[0].category == "test"

    def test_empty_terms_list(self, tmp_path: Path) -> None:
        cfg = tmp_path / "terms.yml"
        cfg.write_text("terms: []\n", encoding="utf-8")
        assert pt.load_terms(cfg) == []


# ---------------------------------------------------------------------------
# scan_terms
# ---------------------------------------------------------------------------

class TestScanTerms:
    def _make_terms(self, name: str, pattern: str, category: str = "test") -> list:
        return [pt.TermDef(name=name, category=category, patterns=[pattern])]

    def test_single_match(self) -> None:
        terms = self._make_terms("web", r"\bweb\b")
        counts, details = pt.scan_terms("Build a web portal", terms)
        assert counts["web"] == 1
        assert details["terms"][0]["term"] == "web"

    def test_multiple_matches_in_text(self) -> None:
        terms = self._make_terms("api", r"\bAPI\b")
        counts, _ = pt.scan_terms("API integration with another API endpoint", terms)
        assert counts["api"] == 2

    def test_no_match_returns_empty(self) -> None:
        terms = self._make_terms("drupal", r"\bDrupal\b")
        counts, details = pt.scan_terms("No CMS mentioned here", terms)
        assert counts["drupal"] == 0
        assert details["terms"] == []

    def test_case_insensitive(self) -> None:
        terms = self._make_terms("cloud", r"\bcloud\b")
        counts, _ = pt.scan_terms("CLOUD hosting services CLOUD", terms)
        assert counts["cloud"] == 2

    def test_category_counts_aggregated(self) -> None:
        terms = [
            pt.TermDef(name="web", category="technology", patterns=[r"\bweb\b"]),
            pt.TermDef(name="api", category="technology", patterns=[r"\bAPI\b"]),
        ]
        _, details = pt.scan_terms("web API integration", terms)
        assert details["categories"]["technology"] >= 2

    def test_matched_terms_sorted_by_count_desc(self) -> None:
        terms = [
            pt.TermDef(name="web", category="tech", patterns=[r"\bweb\b"]),
            pt.TermDef(name="api", category="tech", patterns=[r"\bAPI\b"]),
        ]
        _, details = pt.scan_terms("API API API web", terms)
        assert details["terms"][0]["term"] == "api"

    def test_empty_text_returns_no_matches(self) -> None:
        terms = self._make_terms("web", r"\bweb\b")
        counts, details = pt.scan_terms("", terms)
        assert len(counts) == 0
        assert details["terms"] == []

    def test_empty_terms_list(self) -> None:
        counts, details = pt.scan_terms("web api cloud", [])
        assert len(counts) == 0
        assert details["terms"] == []


# ---------------------------------------------------------------------------
# to_relationships
# ---------------------------------------------------------------------------

class TestToRelationships:
    def _make_row(self, agency: str, notice_type: str, naics: str) -> dict:
        return {
            "Department/Ind.Agency": agency,
            "Type": notice_type,
            "NaicsCode": naics,
        }

    def test_basic_structure(self) -> None:
        records = [self._make_row("DoD", "Solicitation", "541512")]
        result = pt.to_relationships(records)
        assert "nodes" in result
        assert "edges" in result

    def test_nodes_include_agency_and_type(self) -> None:
        records = [self._make_row("DoD", "Solicitation", "541512")]
        result = pt.to_relationships(records)
        node_labels = {n["label"] for n in result["nodes"]}
        assert "DoD" in node_labels
        assert "Solicitation" in node_labels

    def test_edge_weight_increments_for_duplicates(self) -> None:
        records = [
            self._make_row("DoD", "Solicitation", "541512"),
            self._make_row("DoD", "Solicitation", "541512"),
        ]
        result = pt.to_relationships(records)
        agency_type_edges = [
            e for e in result["edges"] if e["kind"] == "agency_to_type"
        ]
        assert any(e["weight"] == 2 for e in agency_type_edges)

    def test_empty_records_returns_empty_lists(self) -> None:
        result = pt.to_relationships([])
        assert result == {"nodes": [], "edges": []}

    def test_missing_fields_use_defaults(self) -> None:
        result = pt.to_relationships([{}])
        labels = {n["label"] for n in result["nodes"]}
        assert "Unknown Agency" in labels


# ---------------------------------------------------------------------------
# build_department_breakdown
# ---------------------------------------------------------------------------

class TestBuildDepartmentBreakdown:
    def _make_row(self, agency: str, notice_type: str = "Solicitation") -> dict:
        return {"Department/Ind.Agency": agency, "Type": notice_type}

    def test_counts_by_agency(self) -> None:
        rows = [
            self._make_row("DoD"),
            self._make_row("DoD"),
            self._make_row("GSA"),
        ]
        result = pt.build_department_breakdown(rows)
        dod = next(r for r in result if r["department"] == "DoD")
        assert dod["total"] == 2

    def test_sorted_by_total_descending(self) -> None:
        rows = [self._make_row("GSA"), self._make_row("DoD"), self._make_row("DoD")]
        result = pt.build_department_breakdown(rows)
        assert result[0]["department"] == "DoD"

    def test_missing_agency_uses_unknown(self) -> None:
        result = pt.build_department_breakdown([{}])
        assert result[0]["department"] == "Unknown Agency"

    def test_empty_records(self) -> None:
        assert pt.build_department_breakdown([]) == []


# ---------------------------------------------------------------------------
# build_date_breakdown
# ---------------------------------------------------------------------------

class TestBuildDateBreakdown:
    def _make_row(self, posted_date: str, notice_type: str = "Solicitation") -> dict:
        return {"PostedDate": posted_date, "Type": notice_type}

    def test_groups_by_date(self) -> None:
        rows = [
            self._make_row("2024-03-15"),
            self._make_row("2024-03-15"),
            self._make_row("2024-03-14"),
        ]
        result = pt.build_date_breakdown(rows)
        march15 = next(r for r in result if r["date"] == "2024-03-15")
        assert march15["total"] == 2

    def test_sorted_by_date_descending(self) -> None:
        rows = [self._make_row("2024-03-14"), self._make_row("2024-03-15")]
        result = pt.build_date_breakdown(rows)
        assert result[0]["date"] == "2024-03-15"

    def test_rows_without_date_skipped(self) -> None:
        rows = [self._make_row(""), self._make_row("2024-03-15")]
        result = pt.build_date_breakdown(rows)
        assert len(result) == 1

    def test_empty_records(self) -> None:
        assert pt.build_date_breakdown([]) == []


# ---------------------------------------------------------------------------
# build_award_company_history
# ---------------------------------------------------------------------------

class TestBuildAwardCompanyHistory:
    def _make_award_row(self, awardee: str, posted: str = "2024-03-01") -> dict:
        return {
            "Type": "Award Notice",
            "Awardee": awardee,
            "PostedDate": posted,
            "AwardDate": "",
        }

    def test_returns_expected_keys(self) -> None:
        result = pt.build_award_company_history([])
        assert "total_companies" in result
        assert "top_companies" in result
        assert "monthly" in result

    def test_empty_input(self) -> None:
        result = pt.build_award_company_history([])
        assert result["total_companies"] == 0
        assert result["top_companies"] == []
        assert result["monthly"] == []


# ---------------------------------------------------------------------------
# extract_top_award_records
# ---------------------------------------------------------------------------

class TestExtractTopAwardRecords:
    def test_filters_to_top_companies(self) -> None:
        rows = [
            {"Type": "Award Notice", "Awardee": "ACME Corp", "NoticeId": "N1"},
            {"Type": "Award Notice", "Awardee": "Other Corp", "NoticeId": "N2"},
        ]
        top = [{"company": "ACME Corp", "awarded": 1}]
        result = pt.extract_top_award_records(rows, top)
        assert isinstance(result, list)

    def test_empty_rows(self) -> None:
        result = pt.extract_top_award_records([], [{"company": "X", "awarded": 1}])
        assert result == []

    def test_empty_top_companies(self) -> None:
        rows = [{"Type": "Award Notice", "Awardee": "ACME", "NoticeId": "N1"}]
        result = pt.extract_top_award_records(rows, [])
        assert result == []


# ---------------------------------------------------------------------------
# write_markdown_opportunities
# ---------------------------------------------------------------------------

class TestWriteMarkdownOpportunities:
    def _make_record(self, notice_id: str = "N001") -> dict:
        return {
            "NoticeId": notice_id,
            "Title": "Test Opportunity",
            "Department/Ind.Agency": "Test Agency",
            "Type": "Solicitation",
            "PostedDate": "2024-03-15",
            "Sol#": "SOL-001",
            "Description": "Test description",
            "Link": "https://sam.gov/opp/N001",
        }

    def test_creates_index_md(self, tmp_path: Path) -> None:
        records = [self._make_record()]
        written = pt.write_markdown_opportunities(records, tmp_path)
        assert written == 1
        md_file = tmp_path / "opportunities" / "N001" / "index.md"
        assert md_file.exists()

    def test_index_md_contains_title(self, tmp_path: Path) -> None:
        records = [self._make_record()]
        pt.write_markdown_opportunities(records, tmp_path)
        content = (tmp_path / "opportunities" / "N001" / "index.md").read_text()
        assert "Test Opportunity" in content

    def test_skips_records_without_notice_id(self, tmp_path: Path) -> None:
        records = [{"Title": "No ID Record", "Department/Ind.Agency": "Agency"}]
        written = pt.write_markdown_opportunities(records, tmp_path)
        assert written == 0

    def test_multiple_records_written(self, tmp_path: Path) -> None:
        records = [self._make_record("N001"), self._make_record("N002")]
        written = pt.write_markdown_opportunities(records, tmp_path)
        assert written == 2

    def test_contact_section_included_when_present(self, tmp_path: Path) -> None:
        record = self._make_record()
        record["PrimaryContactFullname"] = "Jane Doe"
        record["PrimaryContactEmail"] = "jane@agency.gov"
        pt.write_markdown_opportunities([record], tmp_path)
        content = (tmp_path / "opportunities" / "N001" / "index.md").read_text()
        assert "Jane Doe" in content

    def test_awardee_included_when_present(self, tmp_path: Path) -> None:
        record = self._make_record()
        record["Awardee"] = "ACME Corp"
        record["Award$"] = "500000"
        pt.write_markdown_opportunities([record], tmp_path)
        content = (tmp_path / "opportunities" / "N001" / "index.md").read_text()
        assert "ACME Corp" in content

    def test_links_section_included(self, tmp_path: Path) -> None:
        records = [self._make_record()]
        pt.write_markdown_opportunities(records, tmp_path)
        content = (tmp_path / "opportunities" / "N001" / "index.md").read_text()
        assert "sam.gov" in content

    def test_no_link_placeholder_shown(self, tmp_path: Path) -> None:
        record = self._make_record()
        record["Link"] = ""
        pt.write_markdown_opportunities([record], tmp_path)
        content = (tmp_path / "opportunities" / "N001" / "index.md").read_text()
        assert "No links are available" in content
