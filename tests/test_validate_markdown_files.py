"""Tests for validate_markdown_files.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import validate_markdown_files as vmf


class TestValidateMarkdownFiles:
    def _setup_docs(
        self,
        tmp_path: Path,
        records: list[dict],
        write_md: dict[str, str] | None = None,
    ) -> Path:
        """Create a minimal docs directory structure for testing."""
        docs_dir = tmp_path / "docs"
        data_dir = docs_dir / "data"
        data_dir.mkdir(parents=True)

        records_file = data_dir / "today_records.json"
        records_file.write_text(json.dumps(records), encoding="utf-8")

        opps_dir = docs_dir / "opportunities"
        opps_dir.mkdir(parents=True)

        if write_md:
            for notice_id, content in write_md.items():
                md_dir = opps_dir / notice_id
                md_dir.mkdir(parents=True, exist_ok=True)
                (md_dir / "index.md").write_text(content, encoding="utf-8")

        return docs_dir

    def test_missing_records_file_does_not_raise(self, tmp_path: Path) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True)
        # Should print an error but not raise
        vmf.validate_markdown_files(docs_dir)

    def test_valid_markdown_files_counted(self, tmp_path: Path, capsys) -> None:
        records = [{"NoticeId": "ABC123"}]
        docs_dir = self._setup_docs(
            tmp_path,
            records,
            write_md={"ABC123": "# Test Opportunity\n\nContent here."},
        )
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        assert "Valid markdown files: 1" in captured.out

    def test_missing_markdown_file_reported(self, tmp_path: Path, capsys) -> None:
        records = [{"NoticeId": "MISSING123"}]
        docs_dir = self._setup_docs(tmp_path, records, write_md={})
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        assert "Missing markdown files: 1" in captured.out

    def test_empty_markdown_file_reported(self, tmp_path: Path, capsys) -> None:
        records = [{"NoticeId": "EMPTY456"}]
        docs_dir = self._setup_docs(
            tmp_path,
            records,
            write_md={"EMPTY456": ""},
        )
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        assert "Empty markdown files: 1" in captured.out

    def test_records_without_notice_id_skipped(self, tmp_path: Path, capsys) -> None:
        records = [{"NoticeId": ""}, {"NoticeId": None}]
        docs_dir = self._setup_docs(tmp_path, records, write_md={})
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        # No files to find, but no crash either
        assert "Total records: 2" in captured.out
        assert "Valid markdown files: 0" in captured.out

    def test_mixed_valid_missing_empty(self, tmp_path: Path, capsys) -> None:
        records = [
            {"NoticeId": "VALID001"},
            {"NoticeId": "MISSING002"},
            {"NoticeId": "EMPTY003"},
        ]
        docs_dir = self._setup_docs(
            tmp_path,
            records,
            write_md={
                "VALID001": "# Title\nContent",
                "EMPTY003": "",
            },
        )
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        assert "Valid markdown files: 1" in captured.out
        assert "Missing markdown files: 1" in captured.out
        assert "Empty markdown files: 1" in captured.out

    def test_empty_records_list(self, tmp_path: Path, capsys) -> None:
        docs_dir = self._setup_docs(tmp_path, [], write_md={})
        vmf.validate_markdown_files(docs_dir)
        captured = capsys.readouterr()
        assert "Total records: 0" in captured.out
