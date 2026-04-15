"""Accessibility regression tests for docs pages."""

from __future__ import annotations

from pathlib import Path


def test_search_footer_github_link_is_not_color_only() -> None:
    """Footer GitHub link on search page must be distinguishable without color."""
    search_html = (
        Path(__file__).resolve().parents[1] / "docs" / "search.html"
    ).read_text(encoding="utf-8")
    assert 'href="https://github.com/mgifford/sam_gov_md"' in search_html
    assert "text-decoration: underline" in search_html
    assert "text-decoration: none;\">GitHub&nbsp;(mgifford/sam_gov_md)</a>" not in search_html
