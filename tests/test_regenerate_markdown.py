"""Tests for regenerate_markdown_with_attachments.py."""

from __future__ import annotations

from datetime import date

import pytest

import regenerate_markdown_with_attachments as rma


# ---------------------------------------------------------------------------
# parse_date
# ---------------------------------------------------------------------------

class TestParseDate:
    def test_iso_format(self) -> None:
        assert rma.parse_date("2024-03-15") == date(2024, 3, 15)

    def test_us_format(self) -> None:
        assert rma.parse_date("03/15/2024") == date(2024, 3, 15)

    def test_empty_string_returns_none(self) -> None:
        assert rma.parse_date("") is None

    def test_none_returns_none(self) -> None:
        assert rma.parse_date(None) is None  # type: ignore[arg-type]

    def test_whitespace_only_returns_none(self) -> None:
        assert rma.parse_date("   ") is None

    def test_truncates_to_10_chars(self) -> None:
        # Extra time component should be ignored
        assert rma.parse_date("2024-03-15T10:00:00") == date(2024, 3, 15)

    def test_invalid_date_returns_none(self) -> None:
        assert rma.parse_date("not-a-date") is None


# ---------------------------------------------------------------------------
# extract_attachments
# ---------------------------------------------------------------------------

class TestExtractAttachments:
    def test_empty_returns_zero(self) -> None:
        result = rma.extract_attachments("")
        assert result == {"count": 0, "attachments": []}

    def test_none_returns_zero(self) -> None:
        result = rma.extract_attachments(None)  # type: ignore[arg-type]
        assert result == {"count": 0, "attachments": []}

    def test_basic_attachment_label(self) -> None:
        desc = "Attachment 1: Statement of Work.pdf\nOther text"
        result = rma.extract_attachments(desc)
        assert result["count"] > 0
        assert len(result["attachments"]) > 0

    def test_direct_file_reference(self) -> None:
        desc = "Please see Att 1_FAR 52.204-24 Nov 2021.pdf for details."
        result = rma.extract_attachments(desc)
        assert result["count"] > 0
        assert any("pdf" in a.lower() for a in result["attachments"])

    def test_no_duplicates(self) -> None:
        desc = "Attachment 1: spec.pdf\nAttachment 1: spec.pdf"
        result = rma.extract_attachments(desc)
        assert len(result["attachments"]) == len(set(result["attachments"]))

    def test_count_matches_attachments_length(self) -> None:
        desc = "Attachment A: First file\nAttachment B: Second file"
        result = rma.extract_attachments(desc)
        assert result["count"] == len(result["attachments"])


# ---------------------------------------------------------------------------
# _extract_row_fields
# ---------------------------------------------------------------------------

class TestExtractRowFields:
    def _row(self, **kwargs) -> dict:
        defaults = {
            "Title": "Test Opportunity",
            "Department/Ind.Agency": "DEPT OF DEFENSE",
            "Type": "Solicitation",
            "NoticeId": "ABC123",
            "PostedDate": "2024-01-15",
            "Sol#": "W912HZ-24-R-0001",
            "Description": "Test description",
            "Link": "https://sam.gov/opp/ABC123",
            "AdditionalInfoLink": "",
            "Awardee": "",
            "Award$": "",
            "PrimaryContactFullname": "John Smith",
            "PrimaryContactTitle": "Contracting Officer",
            "PrimaryContactEmail": "john.smith@agency.gov",
            "PrimaryContactPhone": "555-1234",
            "SecondaryContactFullname": "",
            "SecondaryContactTitle": "",
            "SecondaryContactEmail": "",
            "SecondaryContactPhone": "",
        }
        defaults.update(kwargs)
        return defaults

    def test_returns_dict(self) -> None:
        result = rma._extract_row_fields(self._row())
        assert isinstance(result, dict)

    def test_title_extracted(self) -> None:
        result = rma._extract_row_fields(self._row(Title="Special Contract"))
        assert result["title"] == "Special Contract"

    def test_agency_extracted(self) -> None:
        result = rma._extract_row_fields(self._row(**{"Department/Ind.Agency": "DEPT OF STATE"}))
        assert result["agency"] == "DEPT OF STATE"

    def test_default_title_when_empty(self) -> None:
        result = rma._extract_row_fields(self._row(Title=""))
        assert result["title"] == "Untitled Opportunity"

    def test_default_agency_when_empty(self) -> None:
        result = rma._extract_row_fields(self._row(**{"Department/Ind.Agency": ""}))
        assert result["agency"] == "Unknown Agency"

    def test_fields_stripped(self) -> None:
        result = rma._extract_row_fields(self._row(Title="  Padded Title  "))
        assert result["title"] == "Padded Title"

    def test_notice_id_extracted(self) -> None:
        result = rma._extract_row_fields(self._row(NoticeId="XYZ789"))
        assert result["notice_id"] == "XYZ789"

    def test_missing_key_defaults_to_empty_string(self) -> None:
        # Passing a row with missing keys
        result = rma._extract_row_fields({})
        assert result["title"] == "Untitled Opportunity"
        assert result["notice_id"] == ""

    def test_awardee_extracted(self) -> None:
        result = rma._extract_row_fields(self._row(Awardee="Acme Corp"))
        assert result["awardee"] == "Acme Corp"

    def test_award_amount_extracted(self) -> None:
        result = rma._extract_row_fields(self._row(**{"Award$": "1,500,000"}))
        assert result["award_amount"] == "1,500,000"
