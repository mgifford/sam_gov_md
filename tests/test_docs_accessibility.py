"""Accessibility-focused checks for static docs pages."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_trends_headings_do_not_skip_levels() -> None:
    trends_html = (REPO_ROOT / "docs" / "trends.html").read_text(encoding="utf-8")

    heading_matches = list(re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", trends_html, flags=re.IGNORECASE))
    assert heading_matches

    first_level = int(heading_matches[0].group(1))
    assert first_level == 1

    top_activity_heading = next(
        match for match in heading_matches if "Top 15 Departments by Activity" in match.group(2)
    )
    assert int(top_activity_heading.group(1)) == 2

    heading_levels = [int(match.group(1)) for match in heading_matches]
    assert heading_levels

    previous_level = heading_levels[0]
    for level in heading_levels[1:]:
        assert level <= previous_level + 1, f"Heading skipped from h{previous_level} to h{level}"
        previous_level = level
