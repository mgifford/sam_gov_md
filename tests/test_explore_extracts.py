"""Tests for explore_extracts.py."""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

import explore_extracts as ee


# ---------------------------------------------------------------------------
# normalize_url
# ---------------------------------------------------------------------------

class TestNormalizeUrl:
    def test_absolute_https_returned_unchanged(self) -> None:
        assert ee.normalize_url("https://sam.gov", "https://other.com/file.zip") == "https://other.com/file.zip"

    def test_absolute_http_returned_unchanged(self) -> None:
        assert ee.normalize_url("https://sam.gov", "http://files.example.com/archive.zip") == "http://files.example.com/archive.zip"

    def test_root_relative_prepends_sam_gov(self) -> None:
        result = ee.normalize_url("https://sam.gov", "/data-services/file.zip")
        assert result == "https://sam.gov/data-services/file.zip"

    def test_empty_href_returns_none(self) -> None:
        assert ee.normalize_url("https://sam.gov", "") is None

    def test_relative_no_slash_returns_none(self) -> None:
        # Relative URLs without a leading slash are not supported
        result = ee.normalize_url("https://sam.gov", "file.zip")
        assert result is None


# ---------------------------------------------------------------------------
# discover_extract_links
# ---------------------------------------------------------------------------

class TestDiscoverExtractLinks:
    def _html(self, hrefs: list[str]) -> str:
        links = "".join(f'<a href="{h}">link</a>' for h in hrefs)
        return f"<html><body>{links}</body></html>"

    def test_finds_zip_links(self) -> None:
        html = self._html(["/extracts/20240115_data.zip"])
        links = ee.discover_extract_links(html)
        assert len(links) == 1
        assert links[0].url == "https://sam.gov/extracts/20240115_data.zip"

    def test_finds_json_links(self) -> None:
        html = self._html(["/extracts/20240115_data.json"])
        links = ee.discover_extract_links(html)
        assert len(links) == 1

    def test_finds_xml_links(self) -> None:
        html = self._html(["/extracts/20240115_data.xml"])
        links = ee.discover_extract_links(html)
        assert len(links) == 1

    def test_ignores_html_links(self) -> None:
        html = self._html(["/page.html", "/document.pdf"])
        links = ee.discover_extract_links(html)
        assert len(links) == 0

    def test_sorted_newest_first(self) -> None:
        html = self._html([
            "/extracts/20240101_data.zip",
            "/extracts/20240315_data.zip",
            "/extracts/20240201_data.zip",
        ])
        links = ee.discover_extract_links(html)
        assert len(links) == 3
        date_keys = [link.date_key for link in links]
        assert date_keys == sorted(date_keys, reverse=True)

    def test_absolute_href_preserved(self) -> None:
        html = self._html(["https://cdn.example.com/20240115.zip"])
        links = ee.discover_extract_links(html)
        assert len(links) == 1
        assert links[0].url == "https://cdn.example.com/20240115.zip"

    def test_empty_html_returns_empty_list(self) -> None:
        links = ee.discover_extract_links("<html><body></body></html>")
        assert links == []

    def test_date_extracted_from_url(self) -> None:
        html = self._html(["/files/2024-03-15_extract.zip"])
        links = ee.discover_extract_links(html)
        assert len(links) == 1
        # Date key should have dashes stripped: 20240315
        assert links[0].date_key == "20240315"


# ---------------------------------------------------------------------------
# iter_json_records
# ---------------------------------------------------------------------------

class TestIterJsonRecords:
    def test_top_level_list(self, tmp_path: Path) -> None:
        data = [{"id": 1}, {"id": 2}]
        path = tmp_path / "records.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = list(ee.iter_json_records(str(path)))
        assert result == data

    def test_opportunities_key(self, tmp_path: Path) -> None:
        data = {"opportunities": [{"id": 1}], "meta": {}}
        path = tmp_path / "records.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = list(ee.iter_json_records(str(path)))
        assert result == [{"id": 1}]

    def test_data_key(self, tmp_path: Path) -> None:
        data = {"data": [{"id": 2}]}
        path = tmp_path / "records.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = list(ee.iter_json_records(str(path)))
        assert result == [{"id": 2}]

    def test_results_key(self, tmp_path: Path) -> None:
        data = {"results": [{"id": 3}]}
        path = tmp_path / "records.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = list(ee.iter_json_records(str(path)))
        assert result == [{"id": 3}]

    def test_unrecognized_structure_raises(self, tmp_path: Path) -> None:
        data = {"unknown_key": [{"id": 1}]}
        path = tmp_path / "records.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(ValueError):
            list(ee.iter_json_records(str(path)))


# ---------------------------------------------------------------------------
# save_markdown
# ---------------------------------------------------------------------------

class TestSaveMarkdown:
    def test_creates_file(self, tmp_path: Path) -> None:
        md_dir = str(tmp_path / "md_output")
        ee.save_markdown(md_dir, "TestFile", "Some content here.")
        files = list(Path(md_dir).iterdir())
        assert len(files) == 1

    def test_file_contains_content(self, tmp_path: Path) -> None:
        md_dir = str(tmp_path / "md_output")
        ee.save_markdown(md_dir, "TestFile", "Hello world")
        result = next(Path(md_dir).iterdir()).read_text(encoding="utf-8")
        assert "Hello world" in result
        assert "# TestFile" in result

    def test_sanitizes_filename(self, tmp_path: Path) -> None:
        md_dir = str(tmp_path / "md_output")
        ee.save_markdown(md_dir, "File Name With Spaces!", "content")
        files = list(Path(md_dir).iterdir())
        assert len(files) == 1
        # Filename should have spaces/special chars replaced
        assert " " not in files[0].name

    def test_none_md_dir_does_nothing(self, tmp_path: Path) -> None:
        # When md_dir is None, no file should be created
        ee.save_markdown(None, "TestFile", "content")
        # No exception, no files created

    def test_creates_directory_if_missing(self, tmp_path: Path) -> None:
        md_dir = str(tmp_path / "nested" / "md_output")
        ee.save_markdown(md_dir, "TestFile", "content")
        assert Path(md_dir).exists()
