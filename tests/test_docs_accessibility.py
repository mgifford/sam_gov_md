"""Accessibility regression tests for docs pages."""

from __future__ import annotations

from pathlib import Path
import re


def test_search_footer_github_link_is_not_color_only() -> None:
    """Footer GitHub link on search page must be distinguishable without color."""
    search_html = (
        Path(__file__).resolve().parents[1] / "docs" / "search.html"
    ).read_text(encoding="utf-8")
    footer_match = re.search(r"<footer.*?</footer>", search_html, re.DOTALL)
    assert footer_match is not None
    footer_html = footer_match.group(0)
    assert (
        '<a href="https://github.com/mgifford/sam_gov_md" '
        'style="color: #0969da; text-decoration: underline;">'
        "GitHub&nbsp;(mgifford/sam_gov_md)</a>"
    ) in footer_html
    assert 'text-decoration: none;">GitHub&nbsp;(mgifford/sam_gov_md)</a>' not in footer_html
