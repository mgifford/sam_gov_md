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


def test_search_footer_link_distinguishable_without_color() -> None:
    search_html = (REPO_ROOT / "docs" / "search.html").read_text(encoding="utf-8")

    footer_match = re.search(
        r"<footer\b[^>]*>.*?</footer>",
        search_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert footer_match is not None

    link_match = re.search(r"<a\b[^>]*>", footer_match.group(0), flags=re.IGNORECASE)
    assert link_match is not None

    opening_tag = link_match.group(0)
    assert re.search(
        r"text-decoration\s*:\s*underline",
        opening_tag,
        flags=re.IGNORECASE,
    ), "Footer GitHub link must be visually distinguishable without relying on color."


def test_search_headings_do_not_skip_levels() -> None:
    search_html = (REPO_ROOT / "docs" / "search.html").read_text(encoding="utf-8")

    heading_matches = list(re.finditer(r"<h([1-6])\b[^>]*>(.*?)</h\1>", search_html, flags=re.IGNORECASE))
    assert heading_matches

    first_level = int(heading_matches[0].group(1))
    assert first_level == 1

    filters_heading = next((match for match in heading_matches if "Filters" in match.group(2)), None)
    assert filters_heading is not None
    assert int(filters_heading.group(1)) == 2

    heading_levels = [int(match.group(1)) for match in heading_matches]
    for previous_level, level in zip(heading_levels, heading_levels[1:]):
        assert level <= previous_level + 1, f"Heading skipped from h{previous_level} to h{level}"
