"""Tests for refresh_ai_vendor_cohort.py."""

from __future__ import annotations

import json

import refresh_ai_vendor_cohort as ra


class _MockResponse:
    """Minimal mock response object for requests.post replacement."""

    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self) -> None:
        """Mock always returns successful status."""

    def json(self) -> dict:
        """Return canned JSON payload."""
        return self._payload


def test_parse_keywords() -> None:
    """Keyword parser should trim and ignore blanks."""
    result = ra.parse_keywords("ai| machine learning | |genai")
    assert result == ["ai", "machine learning", "genai"]


def test_fetch_vendor_candidates_prefers_highest_award() -> None:
    """Duplicate vendor names should keep the largest award amount row."""
    responses = [
        _MockResponse(
            {
                "results": [
                    {
                        "Recipient Name": "Acme AI LLC",
                        "Recipient UEI": "UEI1",
                        "Award Amount": 100.0,
                    },
                    {
                        "Recipient Name": "Other Co",
                        "Recipient UEI": "UEI2",
                        "Award Amount": 50.0,
                    },
                ],
                "page_metadata": {"hasNext": True},
            }
        ),
        _MockResponse(
            {
                "results": [
                    {
                        "Recipient Name": "ACME AI LLC",
                        "Recipient UEI": "UEI1B",
                        "Award Amount": 300.0,
                    }
                ],
                "page_metadata": {"hasNext": False},
            }
        ),
    ]

    def _post(*_args, **_kwargs):
        return responses.pop(0)

    rows = ra.fetch_vendor_candidates(
        start_date="2023-10-01",
        end_date="2026-09-30",
        keywords=["artificial intelligence"],
        max_pages=4,
        page_size=100,
        post_fn=_post,
    )

    assert len(rows) == 2
    assert rows[0]["name"] == "ACME AI LLC"
    assert rows[0]["uei"] == "UEI1B"
    assert rows[0]["award_amount"] == 300.0


def test_write_company_cohort(tmp_path) -> None:
    """Output should be company-list shape with name and UEI keys."""
    vendors = [
        {"name": "Vendor A", "uei": "UEI-A", "award_amount": 500.0},
        {"name": "Vendor B", "uei": "UEI-B", "award_amount": 300.0},
    ]
    out = tmp_path / "cohort.json"
    ra.write_company_cohort(out, vendors, top_n=1)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == [{"name": "Vendor A", "uei": "UEI-A"}]
