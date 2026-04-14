"""Tests for scan_terms.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scan_terms as st


# ---------------------------------------------------------------------------
# count_matches
# ---------------------------------------------------------------------------

class TestCountMatches:
    def test_single_pattern_match(self) -> None:
        assert st.count_matches("web portal", [r"\bweb\b"]) == 1

    def test_multiple_occurrences(self) -> None:
        assert st.count_matches("web web web", [r"\bweb\b"]) == 3

    def test_case_insensitive(self) -> None:
        assert st.count_matches("WEB Web web", [r"\bweb\b"]) == 3

    def test_no_match_returns_zero(self) -> None:
        assert st.count_matches("no match here", [r"\bweb\b"]) == 0

    def test_multiple_patterns_summed(self) -> None:
        count = st.count_matches("API REST API", [r"\bAPI\b", r"\bREST\b"])
        assert count == 3

    def test_empty_text_returns_zero(self) -> None:
        assert st.count_matches("", [r"\bweb\b"]) == 0

    def test_empty_patterns_returns_zero(self) -> None:
        assert st.count_matches("web portal", []) == 0


# ---------------------------------------------------------------------------
# load_terms (scan_terms module version)
# ---------------------------------------------------------------------------

class TestLoadTerms:
    def test_loads_from_real_config(self) -> None:
        config = Path(__file__).parent.parent / "config" / "terms.yml"
        terms = st.load_terms(config)
        assert len(terms) > 0

    def test_each_term_has_name_and_patterns(self) -> None:
        config = Path(__file__).parent.parent / "config" / "terms.yml"
        terms = st.load_terms(config)
        for term in terms:
            assert term.get("name"), "Each term must have a name"
            assert isinstance(term.get("patterns", []), list)

    def test_real_config_includes_acr_patterns(self) -> None:
        config = Path(__file__).parent.parent / "config" / "terms.yml"
        terms = st.load_terms(config)
        acr = next((term for term in terms if term.get("name") == "acr"), None)
        assert acr is not None
        assert st.count_matches("Section 508 ACR required", acr["patterns"]) > 0
        assert (
            st.count_matches("Accessibility Conformance Report included", acr["patterns"]) > 0
        )

    def test_custom_yaml(self, tmp_path: Path) -> None:
        cfg = tmp_path / "terms.yml"
        cfg.write_text(
            "terms:\n  - name: foo\n    patterns:\n      - '\\bfoo\\b'\n",
            encoding="utf-8",
        )
        terms = st.load_terms(cfg)
        assert terms[0]["name"] == "foo"

    def test_empty_terms_list(self, tmp_path: Path) -> None:
        cfg = tmp_path / "terms.yml"
        cfg.write_text("terms: []\n", encoding="utf-8")
        assert st.load_terms(cfg) == []


# ---------------------------------------------------------------------------
# main() integration
# ---------------------------------------------------------------------------

class TestMain:
    def _run_main(
        self,
        tmp_path: Path,
        md_files: dict[str, str],
        terms_yaml: str | None = None,
    ) -> dict:
        md_dir = tmp_path / "md"
        md_dir.mkdir()
        for name, content in md_files.items():
            (md_dir / name).write_text(content, encoding="utf-8")

        if terms_yaml is None:
            terms_yaml = (
                "terms:\n"
                "  - name: web\n"
                "    patterns:\n"
                "      - '\\bweb\\b'\n"
                "    category: technology\n"
            )
        terms_path = tmp_path / "terms.yml"
        terms_path.write_text(terms_yaml, encoding="utf-8")

        output_path = tmp_path / "report.json"

        import sys
        argv_backup = sys.argv[:]
        sys.argv = [
            "scan_terms.py",
            "--md-dir", str(md_dir),
            "--terms", str(terms_path),
            "--output", str(output_path),
        ]
        try:
            st.main()
        finally:
            sys.argv = argv_backup

        return json.loads(output_path.read_text())

    def test_files_scanned_count(self, tmp_path: Path) -> None:
        result = self._run_main(
            tmp_path,
            {"a.md": "web portal", "b.md": "no match"},
        )
        assert result["files_scanned"] == 2

    def test_match_found_in_report(self, tmp_path: Path) -> None:
        result = self._run_main(tmp_path, {"a.md": "web web web"})
        names = [t[0] for t in result["term_counts"]]
        assert "web" in names

    def test_no_matches_returns_empty_files(self, tmp_path: Path) -> None:
        result = self._run_main(tmp_path, {"a.md": "nothing here"})
        assert result["files_with_matches"] == []

    def test_files_sorted_by_match_count_desc(self, tmp_path: Path) -> None:
        result = self._run_main(
            tmp_path,
            {"low.md": "web", "high.md": "web web web web"},
        )
        if len(result["files_with_matches"]) >= 2:
            assert (
                result["files_with_matches"][0]["match_count"]
                >= result["files_with_matches"][1]["match_count"]
            )

    def test_nonexistent_md_dir_raises(self, tmp_path: Path) -> None:
        terms_path = tmp_path / "terms.yml"
        terms_path.write_text("terms: []\n", encoding="utf-8")
        output_path = tmp_path / "report.json"

        import sys
        argv_backup = sys.argv[:]
        sys.argv = [
            "scan_terms.py",
            "--md-dir", str(tmp_path / "nonexistent"),
            "--terms", str(terms_path),
            "--output", str(output_path),
        ]
        try:
            with pytest.raises(FileNotFoundError):
                st.main()
        finally:
            sys.argv = argv_backup

    def test_output_directory_created_if_missing(self, tmp_path: Path) -> None:
        md_dir = tmp_path / "md"
        md_dir.mkdir()
        (md_dir / "a.md").write_text("web", encoding="utf-8")

        terms_path = tmp_path / "terms.yml"
        terms_path.write_text(
            "terms:\n  - name: web\n    patterns:\n      - '\\bweb\\b'\n",
            encoding="utf-8",
        )
        output_path = tmp_path / "nested" / "deep" / "report.json"

        import sys
        argv_backup = sys.argv[:]
        sys.argv = [
            "scan_terms.py",
            "--md-dir", str(md_dir),
            "--terms", str(terms_path),
            "--output", str(output_path),
        ]
        try:
            st.main()
        finally:
            sys.argv = argv_backup

        assert output_path.exists()
