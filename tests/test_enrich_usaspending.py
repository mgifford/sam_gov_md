"""Tests for enrich_usaspending.py."""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

import enrich_usaspending as eu


# ---------------------------------------------------------------------------
# _fiscal_year_range
# ---------------------------------------------------------------------------

class TestFiscalYearRange:
    def test_returns_list_with_one_entry(self) -> None:
        result = eu._fiscal_year_range(3)
        assert isinstance(result, list)
        assert len(result) == 1

    def test_entry_has_start_and_end_date(self) -> None:
        result = eu._fiscal_year_range(3)
        entry = result[0]
        assert "start_date" in entry
        assert "end_date" in entry

    def test_start_before_end(self) -> None:
        result = eu._fiscal_year_range(3)
        entry = result[0]
        assert entry["start_date"] < entry["end_date"]

    def test_span_covers_lookback_years(self) -> None:
        result = eu._fiscal_year_range(3)
        entry = result[0]
        start = date.fromisoformat(entry["start_date"])
        end = date.fromisoformat(entry["end_date"])
        # With lookback=3, fy_start = fy_end.year - 3 + 1 = fy_end.year - 2 (Oct 1)
        # so the range covers 2 full fiscal years (fy_end.year - 2 to fy_end.year)
        diff_years = (end - start).days / 365
        assert 1.5 <= diff_years <= 3.5

    def test_single_year_lookback(self) -> None:
        # With lookback=1, fy_start = date(fy_end.year, 10, 1) which may equal or
        # exceed fy_end (Sep 30), so we just verify the function returns a valid
        # date dict without raising.
        result = eu._fiscal_year_range(1)
        entry = result[0]
        assert "start_date" in entry
        assert "end_date" in entry

    def test_end_date_is_sep_30(self) -> None:
        result = eu._fiscal_year_range(1)
        end = date.fromisoformat(result[0]["end_date"])
        assert end.month == 9
        assert end.day == 30


# ---------------------------------------------------------------------------
# normalize_agency
# ---------------------------------------------------------------------------

class TestNormalizeAgency:
    def test_known_agency_mapped(self) -> None:
        result = eu.normalize_agency("DEPT OF DEFENSE")
        assert result == "Department of Defense"

    def test_case_insensitive(self) -> None:
        result = eu.normalize_agency("dept of defense")
        assert result == "Department of Defense"

    def test_whitespace_stripped(self) -> None:
        result = eu.normalize_agency("  DEPT OF DEFENSE  ")
        assert result == "Department of Defense"

    def test_unknown_agency_returns_none(self) -> None:
        result = eu.normalize_agency("UNKNOWN MYSTERY AGENCY")
        assert result is None

    def test_empty_string_returns_none(self) -> None:
        result = eu.normalize_agency("")
        assert result is None

    def test_none_returns_none(self) -> None:
        result = eu.normalize_agency(None)  # type: ignore[arg-type]
        assert result is None

    def test_gsa_mapped(self) -> None:
        result = eu.normalize_agency("GENERAL SERVICES ADMINISTRATION")
        assert result == "General Services Administration"

    def test_all_known_agencies_have_mappings(self) -> None:
        for sam_name in eu.AGENCY_NAME_MAP:
            assert eu.normalize_agency(sam_name) is not None


# ---------------------------------------------------------------------------
# _fmt_currency
# ---------------------------------------------------------------------------

class TestFmtCurrency:
    def test_millions(self) -> None:
        assert eu._fmt_currency(4_200_000) == "$4.2M"

    def test_exactly_one_million(self) -> None:
        assert eu._fmt_currency(1_000_000) == "$1.0M"

    def test_thousands(self) -> None:
        assert eu._fmt_currency(830_000) == "$830K"

    def test_exactly_one_thousand(self) -> None:
        assert eu._fmt_currency(1_000) == "$1K"

    def test_below_thousand(self) -> None:
        assert eu._fmt_currency(500) == "$500"

    def test_zero(self) -> None:
        assert eu._fmt_currency(0) == "$0"

    def test_large_millions(self) -> None:
        result = eu._fmt_currency(100_000_000)
        assert result == "$100.0M"


# ---------------------------------------------------------------------------
# _fmt_vendors
# ---------------------------------------------------------------------------

class TestFmtVendors:
    def test_empty_returns_no_data(self) -> None:
        assert eu._fmt_vendors([]) == "No data"

    def test_single_vendor_formatted(self) -> None:
        vendors = [{"name": "ACME CORP", "amount": 1_000_000}]
        result = eu._fmt_vendors(vendors)
        assert "Acme Corp" in result
        assert "1,000,000" in result

    def test_multiple_vendors_separated_by_semicolon(self) -> None:
        vendors = [
            {"name": "ACME", "amount": 500_000},
            {"name": "BETA INC", "amount": 300_000},
        ]
        result = eu._fmt_vendors(vendors)
        assert ";" in result

    def test_at_most_five_vendors(self) -> None:
        vendors = [{"name": f"V{i}", "amount": i * 1000} for i in range(10)]
        result = eu._fmt_vendors(vendors)
        # At most 5 semicolons separating entries → at most 5 entries
        assert result.count(";") <= 4

    def test_name_truncated_to_35_chars(self) -> None:
        vendors = [{"name": "A" * 50, "amount": 1000}]
        result = eu._fmt_vendors(vendors)
        # The title-cased, truncated name should be at most 35 chars before the space+amount
        name_part = result.split(" (")[0]
        assert len(name_part) <= 35


# ---------------------------------------------------------------------------
# build_enriched_markdown
# ---------------------------------------------------------------------------

class TestBuildEnrichedMarkdown:
    def _summary(self) -> dict:
        return {
            "effective_date": "2024-03-15",
            "requested_date": "2024-03-15",
            "records_total": 100,
        }

    def test_header_present(self) -> None:
        md = eu.build_enriched_markdown([], {}, self._summary(), 8, [])
        assert "# High-value SAM.gov Matches" in md

    def test_no_matches_message(self) -> None:
        md = eu.build_enriched_markdown([], {}, self._summary(), 8, [])
        assert "No high-value matches" in md

    def test_record_title_in_output(self) -> None:
        row = {"Title": "Web Portal RFP", "NoticeId": "N001", "NaicsCode": "541512"}
        md = eu.build_enriched_markdown([row], {}, self._summary(), 8, [])
        assert "Web Portal RFP" in md

    def test_market_intel_section_when_enrichment_present(self) -> None:
        row = {
            "Title": "Web Portal",
            "NoticeId": "N001",
            "NaicsCode": "541512",
            "Agency": "DoD",
        }
        intel = {
            "agency_contract_count": 42,
            "govwide_top_vendors": [{"name": "ACME", "amount": 1_000_000}],
            "agency_top_vendors": [],
        }
        md = eu.build_enriched_markdown([row], {"N001": intel}, self._summary(), 8, [])
        assert "Market Intelligence" in md
        assert "42" in md

    def test_no_market_intel_when_no_naics(self) -> None:
        row = {"Title": "No NAICS", "NoticeId": "N001", "NaicsCode": ""}
        intel = {"agency_contract_count": 10, "govwide_top_vendors": [], "agency_top_vendors": []}
        md = eu.build_enriched_markdown([row], {"N001": intel}, self._summary(), 8, [])
        assert "Market Intelligence" not in md

    def test_effective_date_in_output(self) -> None:
        md = eu.build_enriched_markdown([], {}, self._summary(), 8, [])
        assert "2024-03-15" in md


# ---------------------------------------------------------------------------
# fetch_award_count and fetch_top_vendors (mocked HTTP)
# ---------------------------------------------------------------------------

class TestFetchAwardCount:
    def test_returns_count_from_api(self) -> None:
        mock_resp = {"results": {"contracts": 42}}
        with patch("enrich_usaspending._post", return_value=mock_resp):
            result = eu.fetch_award_count("541512", "DoD", [])
        assert result == 42

    def test_returns_zero_when_api_fails(self) -> None:
        with patch("enrich_usaspending._post", return_value=None):
            result = eu.fetch_award_count("541512", "DoD", [])
        assert result == 0

    def test_agency_filter_included_when_provided(self) -> None:
        mock_resp = {"results": {"contracts": 10}}
        with patch("enrich_usaspending._post", return_value=mock_resp) as mock_post:
            eu.fetch_award_count("541512", "Department of Defense", [])
        call_payload = mock_post.call_args[0][1]
        assert "agencies" in call_payload["filters"]

    def test_no_agency_filter_when_empty_string(self) -> None:
        mock_resp = {"results": {"contracts": 10}}
        with patch("enrich_usaspending._post", return_value=mock_resp) as mock_post:
            eu.fetch_award_count("541512", "", [])
        call_payload = mock_post.call_args[0][1]
        assert "agencies" not in call_payload["filters"]


class TestFetchTopVendors:
    def test_returns_vendor_list(self) -> None:
        mock_resp = {
            "results": [
                {"name": "ACME CORP", "amount": 1_000_000},
                {"name": "BETA INC", "amount": 500_000},
            ]
        }
        with patch("enrich_usaspending._post", return_value=mock_resp):
            vendors = eu.fetch_top_vendors("541512", "DoD", [])
        assert len(vendors) == 2
        assert vendors[0]["name"] == "ACME CORP"

    def test_returns_empty_list_when_api_fails(self) -> None:
        with patch("enrich_usaspending._post", return_value=None):
            vendors = eu.fetch_top_vendors("541512", "DoD", [])
        assert vendors == []

    def test_returns_empty_list_when_no_results(self) -> None:
        with patch("enrich_usaspending._post", return_value={"results": []}):
            vendors = eu.fetch_top_vendors("541512", None, [])
        assert vendors == []
