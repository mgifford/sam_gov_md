"""Accessibility-focused checks for static docs pages."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_trends_headings_do_not_skip_levels() -> None:
    trends_html = (REPO_ROOT / "docs" / "trends.html").read_text(encoding="utf-8")

    assert "<h2>Top 15 Departments by Activity</h2>" in trends_html

    heading_levels = [int(level) for level in re.findall(r"<h([1-6])\b", trends_html, flags=re.IGNORECASE)]
    assert heading_levels

    previous_level = heading_levels[0]
    for level in heading_levels[1:]:
        assert level - previous_level <= 1
        previous_level = level
