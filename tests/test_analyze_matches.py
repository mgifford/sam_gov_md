"""Tests for analyze_matches.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import analyze_matches as am


# ---------------------------------------------------------------------------
# load_json_for_file
# ---------------------------------------------------------------------------

class TestLoadJsonForFile:
    def test_returns_dict_when_file_exists(self, tmp_path: Path) -> None:
        data = {"SOLNBR": "SOL-001", "SUBJECT": "Test"}
        json_file = tmp_path / "my_record.sample.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")
        result = am.load_json_for_file("my_record.md", tmp_path)
        assert result == data

    def test_returns_empty_dict_when_file_missing(self, tmp_path: Path) -> None:
        result = am.load_json_for_file("nonexistent.md", tmp_path)
        assert result == {}

    def test_base_name_without_md_extension(self, tmp_path: Path) -> None:
        data = {"AGENCY": "DoD"}
        json_file = tmp_path / "opp123.sample.json"
        json_file.write_text(json.dumps(data), encoding="utf-8")
        result = am.load_json_for_file("opp123.md", tmp_path)
        assert result["AGENCY"] == "DoD"


# ---------------------------------------------------------------------------
# extract_snippet
# ---------------------------------------------------------------------------

class TestExtractSnippet:
    def test_returns_snippet_around_match(self) -> None:
        text = "Introduction. " + ("padding " * 30) + "web portal" + (" more" * 30)
        snippet = am.extract_snippet(text, r"\bweb\b")
        assert "web" in snippet

    def test_no_match_returns_empty_string(self) -> None:
        snippet = am.extract_snippet("no relevant terms here", r"\bweb\b")
        assert snippet == ""

    def test_snippet_has_ellipsis_prefix_and_suffix(self) -> None:
        text = " context " * 50 + " web " + " more context " * 50
        snippet = am.extract_snippet(text, r"\bweb\b")
        assert snippet.startswith("...")
        assert snippet.endswith("...")

    def test_match_at_start_no_negative_index(self) -> None:
        text = "web portal development"
        snippet = am.extract_snippet(text, r"\bweb\b")
        assert "web" in snippet

    def test_match_at_end_no_overflow(self) -> None:
        text = "development of a new web"
        snippet = am.extract_snippet(text, r"\bweb\b")
        assert "web" in snippet

    def test_case_insensitive_match(self) -> None:
        snippet = am.extract_snippet("WEB portal", r"\bweb\b")
        assert "WEB" in snippet

    def test_custom_context_size(self) -> None:
        text = " word " * 100 + " api " + " word " * 100
        snippet_small = am.extract_snippet(text, r"\bapi\b", context=10)
        snippet_large = am.extract_snippet(text, r"\bapi\b", context=100)
        assert len(snippet_small) < len(snippet_large)


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain:
    def _setup(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        md_dir = tmp_path / "md"
        json_dir = tmp_path / "json"
        md_dir.mkdir()
        json_dir.mkdir()
        return tmp_path, md_dir, json_dir

    def _write_report(self, tmp_path: Path, files_with_matches: list[dict]) -> Path:
        report = {
            "files_scanned": len(files_with_matches),
            "term_counts": [["web", 5]],
            "files_with_matches": files_with_matches,
        }
        p = tmp_path / "report.json"
        p.write_text(json.dumps(report), encoding="utf-8")
        return p

    def _run_main(
        self,
        tmp_path: Path,
        md_dir: Path,
        json_dir: Path,
        report_path: Path,
    ) -> str:
        output_path = tmp_path / "out.md"
        import sys
        argv_backup = sys.argv[:]
        sys.argv = [
            "analyze_matches.py",
            "--report", str(report_path),
            "--md-dir", str(md_dir),
            "--json-dir", str(json_dir),
            "--output", str(output_path),
        ]
        try:
            am.main()
        finally:
            sys.argv = argv_backup
        return output_path.read_text(encoding="utf-8")

    def test_output_contains_header(self, tmp_path: Path) -> None:
        _, md_dir, json_dir = self._setup(tmp_path)
        report = self._write_report(tmp_path, [])
        content = self._run_main(tmp_path, md_dir, json_dir, report)
        assert "# Top ICT/Digital Project Matches" in content

    def test_term_frequency_section_present(self, tmp_path: Path) -> None:
        _, md_dir, json_dir = self._setup(tmp_path)
        report = self._write_report(tmp_path, [])
        content = self._run_main(tmp_path, md_dir, json_dir, report)
        assert "## Term Frequency Summary" in content

    def test_record_section_included(self, tmp_path: Path) -> None:
        _, md_dir, json_dir = self._setup(tmp_path)
        (md_dir / "opp1.md").write_text(
            "This is a web portal opportunity.", encoding="utf-8"
        )
        report = self._write_report(
            tmp_path,
            [
                {
                    "file": "opp1.md",
                    "match_count": 5,
                    "matches": [{"term": "web", "count": 5}],
                }
            ],
        )
        content = self._run_main(tmp_path, md_dir, json_dir, report)
        assert "opp1.md" in content

    def test_metadata_from_json_included(self, tmp_path: Path) -> None:
        _, md_dir, json_dir = self._setup(tmp_path)
        (md_dir / "opp1.md").write_text("web", encoding="utf-8")
        meta = {"SOLNBR": "SOL-999", "AGENCY": "NASA"}
        (json_dir / "opp1.sample.json").write_text(json.dumps(meta), encoding="utf-8")
        report = self._write_report(
            tmp_path,
            [{"file": "opp1.md", "match_count": 1, "matches": [{"term": "web", "count": 1}]}],
        )
        content = self._run_main(tmp_path, md_dir, json_dir, report)
        assert "SOL-999" in content

    def test_output_file_created(self, tmp_path: Path) -> None:
        _, md_dir, json_dir = self._setup(tmp_path)
        report = self._write_report(tmp_path, [])
        self._run_main(tmp_path, md_dir, json_dir, report)
        assert (tmp_path / "out.md").exists()
