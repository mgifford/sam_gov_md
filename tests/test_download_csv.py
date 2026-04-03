"""Tests for download_csv.py."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

import download_csv as dc


class TestDownloadCsv:
    def test_successful_download_creates_file(self, tmp_path: Path) -> None:
        dest = str(tmp_path / "output.csv")

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b"col1,col2\n", b"val1,val2\n"]

        with patch("requests.get", return_value=mock_resp):
            dc.download_csv("https://example.com/data.csv", dest)

        assert Path(dest).exists()
        content = Path(dest).read_bytes()
        assert b"col1,col2" in content

    def test_raises_after_all_retries_fail(self, tmp_path: Path) -> None:
        dest = str(tmp_path / "output.csv")

        with patch("requests.get", side_effect=Exception("network error")):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError, match="Failed to download"):
                    dc.download_csv("https://example.com/data.csv", dest, retries=2)

    def test_retries_on_failure_then_succeeds(self, tmp_path: Path) -> None:
        dest = str(tmp_path / "output.csv")

        success_resp = MagicMock()
        success_resp.__enter__ = MagicMock(return_value=success_resp)
        success_resp.__exit__ = MagicMock(return_value=False)
        success_resp.raise_for_status = MagicMock()
        success_resp.headers = {}
        success_resp.iter_content.return_value = [b"data"]

        with patch(
            "requests.get",
            side_effect=[Exception("fail"), success_resp],
        ):
            with patch("time.sleep"):
                dc.download_csv("https://example.com/data.csv", dest, retries=2)

        assert Path(dest).exists()

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        dest = str(tmp_path / "subdir" / "output.csv")

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {}
        mock_resp.iter_content.return_value = [b"data"]

        with patch("requests.get", return_value=mock_resp):
            dc.download_csv("https://example.com/data.csv", dest)

        assert Path(dest).parent.exists()

    def test_content_length_header_logged(self, tmp_path: Path, capsys) -> None:
        dest = str(tmp_path / "output.csv")

        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.raise_for_status = MagicMock()
        mock_resp.headers = {"Content-Length": str(2 * 1024 * 1024)}
        mock_resp.iter_content.return_value = [b"data"]

        with patch("requests.get", return_value=mock_resp):
            dc.download_csv("https://example.com/data.csv", dest)

        captured = capsys.readouterr()
        assert "MB" in captured.out
