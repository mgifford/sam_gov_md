"""Accessibility-focused checks for static docs pages."""

from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent

_HEADING_RE = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.IGNORECASE)


def _assert_headings_do_not_skip_levels(html: str) -> list[re.Match[str]]:
    """Parse heading tags from *html*, assert h1 is first, and no level skips."""
    heading_matches = list(_HEADING_RE.finditer(html))
    assert heading_matches, "No heading elements found"
    assert int(heading_matches[0].group(1)) == 1, (
        f"First heading should be h1, got h{heading_matches[0].group(1)}"
    )
    heading_levels = [int(m.group(1)) for m in heading_matches]
    for previous_level, level in zip(heading_levels, heading_levels[1:]):
        assert level <= previous_level + 1, f"Heading skipped from h{previous_level} to h{level}"
    return heading_matches


def test_trends_headings_do_not_skip_levels() -> None:
    trends_html = (REPO_ROOT / "docs" / "trends.html").read_text(encoding="utf-8")

    heading_matches = _assert_headings_do_not_skip_levels(trends_html)

    top_activity_heading = next(
        match for match in heading_matches if "Top 15 Departments by Activity" in match.group(2)
    )
    assert int(top_activity_heading.group(1)) == 2


def _assert_footer_link_has_underline(html: str, page_name: str) -> None:
    """Assert that the first link in the footer of *html* has text-decoration:underline."""
    footer_match = re.search(
        r"<footer\b[^>]*>.*?</footer>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert footer_match is not None, f"{page_name} must have a <footer> element"

    link_match = re.search(r"<a\b[^>]*>", footer_match.group(0), flags=re.IGNORECASE)
    assert link_match is not None, f"{page_name} footer must contain a link"

    opening_tag = link_match.group(0)
    assert re.search(
        r"text-decoration\s*:\s*underline",
        opening_tag,
        flags=re.IGNORECASE,
    ), f"{page_name} footer GitHub link must be visually distinguishable without relying on color."


def test_search_footer_link_distinguishable_without_color() -> None:
    search_html = (REPO_ROOT / "docs" / "search.html").read_text(encoding="utf-8")
    _assert_footer_link_has_underline(search_html, "search.html")


def test_index_footer_link_distinguishable_without_color() -> None:
    index_html = (REPO_ROOT / "docs" / "index.html").read_text(encoding="utf-8")
    _assert_footer_link_has_underline(index_html, "index.html")


def test_trends_footer_link_distinguishable_without_color() -> None:
    trends_html = (REPO_ROOT / "docs" / "trends.html").read_text(encoding="utf-8")
    _assert_footer_link_has_underline(trends_html, "trends.html")


def test_search_headings_do_not_skip_levels() -> None:
    search_html = (REPO_ROOT / "docs" / "search.html").read_text(encoding="utf-8")

    heading_matches = _assert_headings_do_not_skip_levels(search_html)

    filters_heading = next((match for match in heading_matches if "Filters" in match.group(2)), None)
    assert filters_heading is not None
    assert int(filters_heading.group(1)) == 2


def test_index_headings_do_not_skip_levels() -> None:
    index_html = (REPO_ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    heading_matches = _assert_headings_do_not_skip_levels(index_html)

    toc_heading = next((match for match in heading_matches if "Table of Contents" in match.group(2)), None)
    assert toc_heading is not None, "Table of Contents heading not found"
    assert int(toc_heading.group(1)) == 2, (
        f"Table of Contents should be h2, got h{toc_heading.group(1)}"
    )


def test_time_to_award_headings_do_not_skip_levels() -> None:
    html = (REPO_ROOT / "docs" / "time_to_award.html").read_text(encoding="utf-8")

    heading_matches = _assert_headings_do_not_skip_levels(html)

    officers_heading = next(
        (m for m in heading_matches if "Officer" in m.group(2)), None
    )
    assert officers_heading is not None
    assert int(officers_heading.group(1)) == 2


def test_time_to_award_footer_link_distinguishable_without_color() -> None:
    html = (REPO_ROOT / "docs" / "time_to_award.html").read_text(encoding="utf-8")
    _assert_footer_link_has_underline(html, "time_to_award.html")


def test_time_to_award_has_landmark_elements() -> None:
    html = (REPO_ROOT / "docs" / "time_to_award.html").read_text(encoding="utf-8")
    assert re.search(r"<header\b", html, re.IGNORECASE), (
        "time_to_award.html must have a <header> landmark element"
    )
    assert re.search(r"<main\b", html, re.IGNORECASE), (
        "time_to_award.html must have a <main> landmark element"
    )
    assert re.search(r"<footer\b", html, re.IGNORECASE), (
        "time_to_award.html must have a <footer> landmark element"
    )


def test_index_all_content_in_landmarks() -> None:
    """Regression: all visible page content must be within landmark elements.

    Guards against the axe 'region' rule violation where content (e.g.
    ``<div class="container">``) appears outside a landmark region such as
    ``<header>``, ``<main>``, or ``<footer>``.
    """
    index_html = (REPO_ROOT / "docs" / "index.html").read_text(encoding="utf-8")

    # All three landmark elements must be present.
    assert re.search(r"<header\b", index_html, re.IGNORECASE), (
        "index.html must have a <header> landmark element (role=banner)"
    )
    assert re.search(r"<main\b", index_html, re.IGNORECASE), (
        "index.html must have a <main> landmark element"
    )
    assert re.search(r"<footer\b", index_html, re.IGNORECASE), (
        "index.html must have a <footer> landmark element (role=contentinfo)"
    )

    # No <div class="container"> should appear between </header> and <main>
    # (i.e. outside any landmark region).
    between_header_main = re.search(
        r"</header\s*>(.*?)<main\b",
        index_html,
        re.DOTALL | re.IGNORECASE,
    )
    if between_header_main:
        gap = between_header_main.group(1)
        assert not re.search(
            r"<div\b[^>]*\bclass=[\"'][^\"']*container", gap, re.IGNORECASE
        ), "A <div class='container'> appears between </header> and <main> — outside any landmark"

    # No <div class="container"> should appear between </main> and <footer>.
    between_main_footer = re.search(
        r"</main\s*>(.*?)<footer\b",
        index_html,
        re.DOTALL | re.IGNORECASE,
    )
    if between_main_footer:
        gap = between_main_footer.group(1)
        assert not re.search(
            r"<div\b[^>]*\bclass=[\"'][^\"']*container", gap, re.IGNORECASE
        ), "A <div class='container'> appears between </main> and <footer> — outside any landmark"
