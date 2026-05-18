#!/usr/bin/env python3
"""Build a recompete risk dataset for a selected contractor cohort.

This script is intentionally provider-oriented so it can run now with
USASpending-only data, while remaining easy to connect to external
toolchains (for example MCP-backed usaspending/ecfr/gsa_calc clients).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

import requests

logger = logging.getLogger(__name__)

USASPENDING_ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
EARLIEST_USASPENDING_DATE = "2007-10-01"
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0
CONTRACT_AWARD_TYPE_CODES = ["A", "B", "C", "D"]
ECFR_FAR_PART_19_5_URL = "https://www.ecfr.gov/current/title-48/chapter-1/subchapter-C/part-19"
GSA_CALC_ENDPOINT = "https://api.gsa.gov/acquisition/calc/v3/api/ceilingrates/"
BLS_ENDPOINT_V1 = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
BLS_ENDPOINT_V2 = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
BLS_DEFAULT_YEAR = "2024"
COHORT_COMPANY_FILES = {
    "dsc": "config/company_lists/dsc.json",
    "ai": "config/company_lists/ai_vendors_federal.json",
}

# Conservative fallback medians; replace with live gsa_calc integration when
# available. Values are hourly rates in USD.
FALLBACK_RATE_BENCHMARKS = {
    "Software Engineer": {"p50": 165.0, "p75": 205.0},
    "DevSecOps Engineer": {"p50": 185.0, "p75": 225.0},
    "Data Scientist": {"p50": 190.0, "p75": 240.0},
    "Business Analyst": {"p50": 130.0, "p75": 165.0},
    "UX Designer": {"p50": 145.0, "p75": 180.0},
    "Program Manager": {"p50": 170.0, "p75": 220.0},
    "Cybersecurity Analyst": {"p50": 180.0, "p75": 230.0},
    "General IT Services": {"p50": 145.0, "p75": 185.0},
}

LABOR_CATEGORY_TO_SOC = {
    "Software Engineer": "151252",
    "DevSecOps Engineer": "151252",
    "Data Scientist": "152051",
    "Business Analyst": "131111",
    "UX Designer": "273042",
    "Program Manager": "131082",
    "Cybersecurity Analyst": "151212",
    "General IT Services": "151211",
}


@dataclass(frozen=True)
class Company:
    """A target company entry for cohort analysis."""

    name: str
    uei: str | None = None


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Build recompete risk outputs")
    parser.add_argument(
        "--cohort",
        choices=sorted(COHORT_COMPANY_FILES.keys()),
        help="Named company cohort preset (overrides --companies-file when set).",
    )
    parser.add_argument(
        "--companies-file",
        default="config/company_lists/dsc.json",
        help="JSON file containing company list (names and optional UEIs).",
    )
    parser.add_argument(
        "--fy-start",
        default="2024-10-01",
        help="FY window start date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--fy-end",
        default="2026-09-30",
        help="FY window end date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--max-pages-per-company",
        type=int,
        default=8,
        help="USASpending pages fetched per company before stopping.",
    )
    parser.add_argument(
        "--output-json",
        default="data/today/recompetes.json",
        help="Output JSON path (ParaCharts shape).",
    )
    parser.add_argument(
        "--output-md",
        default="data/today/summary.md",
        help="Output markdown summary path.",
    )
    parser.add_argument(
        "--output-docs-json",
        default="docs/data/recompetes.json",
        help="Optional docs JSON output path for GitHub Pages visualization.",
    )
    parser.add_argument(
        "--output-paracharts-spec",
        default="docs/data/recompetes_paracharts_specs.json",
        help="ParaCharts manifest/spec JSON output path.",
    )
    parser.add_argument(
        "--benchmark-mode",
        choices=["auto", "fallback"],
        default="auto",
        help="Rate benchmark mode: 'auto' uses GSA CALC + BLS with fallback, 'fallback' uses local defaults only.",
    )
    parser.add_argument(
        "--bls-burden-multiplier",
        type=float,
        default=2.0,
        help="Multiplier applied to BLS hourly median to estimate fully burdened contractor rate.",
    )
    return parser.parse_args()


def load_companies(path: Path) -> list[Company]:
    """Load companies from a JSON list.

    Accepted JSON formats:
    - ["Company A", "Company B"]
    - [{"name": "Company A", "uei": "ABC123..."}, ...]
    - [{"company_name": "Company A", "sector": "..."}, ...]
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Company file must be a JSON array")

    companies: list[Company] = []
    for item in payload:
        if isinstance(item, str):
            name = item.strip()
            if name:
                companies.append(Company(name=name))
            continue
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("company_name") or "").strip()
            uei_raw = str(item.get("uei", "")).strip()
            if name:
                companies.append(Company(name=name, uei=uei_raw or None))

    deduped: list[Company] = []
    seen = set()
    for company in companies:
        key = company.name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(company)
    return deduped


def resolve_companies_file(cohort: str | None, companies_file: str) -> Path:
    """Resolve final company-list path from cohort preset or explicit file."""
    if cohort:
        return Path(COHORT_COMPANY_FILES[cohort])
    return Path(companies_file)


def parse_date(value: str | None) -> date | None:
    """Parse common API date formats into a date value."""
    if not value:
        return None
    raw = value.strip()
    match = re.match(r"^(\d{4}-\d{2}-\d{2})", raw)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def quarter_from_date(value: date) -> str:
    """Map calendar month to Q1-Q4 for ParaCharts output."""
    month_to_q = {
        1: "Q1",
        2: "Q1",
        3: "Q1",
        4: "Q2",
        5: "Q2",
        6: "Q2",
        7: "Q3",
        8: "Q3",
        9: "Q3",
        10: "Q4",
        11: "Q4",
        12: "Q4",
    }
    return month_to_q[value.month]


def is_small_business_set_aside(value: str | None) -> bool:
    """Return True when set-aside text indicates a small-business action."""
    if not value:
        return False
    text = value.lower()
    return "small" in text and ("set aside" in text or "set-aside" in text)


def far_rule_of_two_note(is_set_aside: bool) -> str:
    """Return a compact FAR 19.5 note for recompete screening."""
    if is_set_aside:
        return (
            "Small Business Set-Aside detected; FAR 19.502-2 (Rule of Two) "
            "likely applies to recompete strategy."
        )
    return "No Small Business Set-Aside signal detected in award metadata."


def classify_vendor_depth_signal(small_vendor_count: int) -> str:
    """Classify Rule-of-Two market depth confidence by small vendor count."""
    if small_vendor_count >= 5:
        return "high"
    if small_vendor_count >= 2:
        return "medium"
    if small_vendor_count >= 1:
        return "low"
    return "insufficient"


def _should_retry_status(status_code: int | None) -> bool:
    """Return True when an HTTP status likely reflects transient infrastructure issues."""
    return status_code == 429 or (status_code is not None and status_code >= 500)


def _response_status_code(response: requests.Response | None) -> int | None:
    """Extract an HTTP status code from a response object when present."""
    return response.status_code if response is not None else None


def _retry_delay_seconds(attempt: int, backoff: float) -> float:
    """Return exponential backoff seconds for a 1-indexed failed attempt."""
    return backoff * (2 ** (attempt - 1))


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = REQUEST_TIMEOUT,
    retries: int = REQUEST_RETRIES,
    backoff: float = RETRY_BACKOFF_SECONDS,
    request_fn: Callable[..., requests.Response] = requests.request,
) -> dict[str, Any] | None:
    """Return parsed JSON from an HTTP request, retrying transient failures."""
    last_error: Exception | None = None

    for attempt_index in range(retries):
        attempt = attempt_index + 1
        try:
            response = request_fn(method, url, json=payload, params=params, timeout=timeout)
            status_code = _response_status_code(response)
            if _should_retry_status(status_code):
                raise requests.HTTPError(
                    f"Retryable HTTP status {status_code}",
                    response=response,
                )
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as exc:
            last_error = exc
            status_code = _response_status_code(exc.response)
            if not _should_retry_status(status_code):
                logger.warning("Request to %s failed with status %s: %s", url, status_code, exc)
                return None
        except (requests.RequestException, ValueError) as exc:
            last_error = exc

        if attempt < retries:
            sleep_for = _retry_delay_seconds(attempt, backoff)
            logger.warning(
                "Request to %s failed on attempt %s/%s: %s. Retrying in %.0fs.",
                url,
                attempt,
                retries,
                last_error,
                sleep_for,
            )
            time.sleep(sleep_for)

    logger.warning("Request to %s failed after %s attempts: %s", url, retries, last_error)
    return None


def fetch_vendor_depth_signal(
    naics_code: str,
    awarding_agency: str,
    fy_end: date,
    max_pages: int = 2,
) -> dict[str, Any]:
    """Estimate small-business vendor depth signal from recent USASpending awards."""
    if not naics_code:
        return {
            "small_business_vendor_count_3y": 0,
            "total_vendor_count_3y": 0,
            "vendor_depth_signal": "not-available",
        }

    lookback_start = date(fy_end.year - 2, 10, 1)
    filters: dict[str, Any] = {
        "time_period": [{"start_date": str(lookback_start), "end_date": str(fy_end)}],
        "award_type_codes": CONTRACT_AWARD_TYPE_CODES,
        "naics_codes": [naics_code],
    }
    if awarding_agency:
        filters["agencies"] = [{"type": "awarding", "tier": "toptier", "name": awarding_agency}]

    fields = ["Recipient Name", "Type Set Aside"]
    total_vendors: set[str] = set()
    small_vendors: set[str] = set()

    for page in range(1, max_pages + 1):
        payload = {
            "fields": fields,
            "filters": filters,
            "page": page,
            "limit": 100,
            "sort": "Recipient Name",
            "order": "asc",
            "subawards": False,
        }
        body = _request_json("post", USASPENDING_ENDPOINT, payload=payload)
        if not body:
            return {
                "small_business_vendor_count_3y": 0,
                "total_vendor_count_3y": 0,
                "vendor_depth_signal": "unknown",
            }

        rows = body.get("results", [])
        for row in rows:
            recipient = str(row.get("Recipient Name") or "").strip()
            if not recipient:
                continue
            total_vendors.add(recipient)
            if is_small_business_set_aside(str(row.get("Type Set Aside") or "")):
                small_vendors.add(recipient)

        if not body.get("page_metadata", {}).get("hasNext"):
            break

    small_count = len(small_vendors)
    return {
        "small_business_vendor_count_3y": small_count,
        "total_vendor_count_3y": len(total_vendors),
        "vendor_depth_signal": classify_vendor_depth_signal(small_count),
    }


def build_rule_of_two_evidence(
    is_set_aside: bool,
    naics_code: str,
    awarding_agency: str,
    fy_end: date,
    vendor_depth_provider: Callable[[str, str, date], dict[str, Any]],
) -> dict[str, Any]:
    """Build a compact Rule-of-Two evidence object for downstream reporting."""
    if not is_set_aside:
        return {
            "far_part": "19.5",
            "ecfr_url": ECFR_FAR_PART_19_5_URL,
            "rule_of_two_applicable": False,
            "vendor_depth_signal": "not-applicable",
            "small_business_vendor_count_3y": 0,
            "total_vendor_count_3y": 0,
            "evidence_note": "Award is not marked as a small-business set-aside.",
        }

    depth = vendor_depth_provider(naics_code, awarding_agency, fy_end)
    signal = str(depth.get("vendor_depth_signal") or "unknown")
    small_count = int(depth.get("small_business_vendor_count_3y") or 0)
    total_count = int(depth.get("total_vendor_count_3y") or 0)

    return {
        "far_part": "19.5",
        "ecfr_url": ECFR_FAR_PART_19_5_URL,
        "rule_of_two_applicable": True,
        "vendor_depth_signal": signal,
        "small_business_vendor_count_3y": small_count,
        "total_vendor_count_3y": total_count,
        "evidence_note": (
            "Rule-of-Two screening uses recent USASpending vendor depth for the same "
            "NAICS and awarding agency as a proxy market signal."
        ),
    }


def infer_labor_category(description: str | None) -> str:
    """Infer a primary labor category from text using simple keyword rules."""
    text = (description or "").lower()
    category_patterns: list[tuple[str, str]] = [
        (r"devsecops|ci/cd|pipeline|kubernetes", "DevSecOps Engineer"),
        (r"software|application development|coding|developer", "Software Engineer"),
        (r"data science|machine learning|analytics", "Data Scientist"),
        (r"ux|user experience|human-centered|design", "UX Designer"),
        (r"program management|project management|pmo", "Program Manager"),
        (r"cyber|security operations|zero trust", "Cybersecurity Analyst"),
        (r"business analysis|requirements", "Business Analyst"),
    ]
    for pattern, category in category_patterns:
        if re.search(pattern, text):
            return category
    return "General IT Services"


def _extract_hourly_rate_from_text(description: str | None) -> float | None:
    """Extract an hourly rate when award text includes explicit $/hr notation."""
    text = description or ""
    pattern = re.compile(r"\$\s*(\d{2,4}(?:\.\d{1,2})?)\s*(?:/|per\s+)?(?:hr|hour)", re.IGNORECASE)
    match = pattern.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_gsa_percentile(values: dict[str, Any], percentile: str) -> float | None:
    """Read percentile values with robust key handling."""
    for key in (percentile, f"{percentile}.0", int(float(percentile)), float(percentile)):
        if key in values:
            try:
                return float(values[key])
            except (TypeError, ValueError):
                return None
    return None


def _fetch_gsa_calc_stats(labor_category: str) -> dict[str, Any] | None:
    """Query public GSA CALC endpoint and return p50/p75 stats."""
    params = {
        "keyword": labor_category,
        "page": 1,
        "page_size": 10,
        "ordering": "current_price",
        "sort": "asc",
    }
    url = f"{GSA_CALC_ENDPOINT}?{urllib.parse.urlencode(params)}"
    payload = _request_json("get", url)
    if not payload:
        return None

    aggs = payload.get("aggregations", {}) if isinstance(payload, dict) else {}
    wage_stats = aggs.get("wage_stats", {}) if isinstance(aggs, dict) else {}
    histogram = aggs.get("histogram_percentiles", {}) if isinstance(aggs, dict) else {}
    percentile_values = histogram.get("values", {}) if isinstance(histogram, dict) else {}

    try:
        total_rates = int(wage_stats.get("count") or payload.get("hits", {}).get("total", {}).get("value") or 0)
    except (TypeError, ValueError, AttributeError):
        total_rates = 0

    p50 = _parse_gsa_percentile(percentile_values, "50")
    p75 = _parse_gsa_percentile(percentile_values, "75")
    if p50 is None and p75 is None:
        return None

    return {
        "p50": p50,
        "p75": p75,
        "sample_size": total_rates,
    }


def _fetch_bls_hourly_median(labor_category: str) -> float | None:
    """Query BLS OEWS for hourly median wage using SOC mapped to labor category."""
    soc = LABOR_CATEGORY_TO_SOC.get(labor_category)
    if not soc:
        return None

    series_id = f"OEUN0000000000000{soc}09"
    api_key = os.environ.get("BLS_API_KEY", "").strip()
    endpoint = BLS_ENDPOINT_V2 if api_key else BLS_ENDPOINT_V1
    payload: dict[str, Any] = {
        "seriesid": [series_id],
        "startyear": BLS_DEFAULT_YEAR,
        "endyear": BLS_DEFAULT_YEAR,
    }
    if api_key:
        payload["registrationkey"] = api_key

    body = _request_json("post", endpoint, payload=payload)
    if not body:
        return None

    series = (((body or {}).get("Results") or {}).get("series") or [])
    if not isinstance(series, list) or not series:
        return None
    data = (series[0] or {}).get("data") or []
    if not isinstance(data, list) or not data:
        return None
    value = data[0].get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class RateBenchmarkResolver:
    """Resolve benchmark rates from live sources with fallback defaults."""

    def __init__(self, mode: str, bls_burden_multiplier: float) -> None:
        self.mode = mode
        self.bls_burden_multiplier = bls_burden_multiplier
        self._cache: dict[str, dict[str, Any]] = {}

    def resolve(self, labor_category: str, description: str | None) -> tuple[float, dict[str, Any]]:
        """Return benchmark difference percent and source metadata."""
        if labor_category in self._cache:
            benchmark = self._cache[labor_category]
        else:
            benchmark = self._resolve_fresh(labor_category)
            self._cache[labor_category] = benchmark

        benchmark_rate = benchmark.get("benchmark_rate")
        if not benchmark_rate or benchmark_rate <= 0:
            return 0.0, benchmark

        incumbent_rate = _extract_hourly_rate_from_text(description)
        if incumbent_rate:
            diff = ((incumbent_rate - benchmark_rate) / benchmark_rate) * 100.0
            benchmark = {**benchmark, "comparison_mode": "incumbent_vs_market", "incumbent_rate": incumbent_rate}
            return round(diff, 2), benchmark

        p75 = benchmark.get("gsa_p75")
        if p75:
            diff = ((p75 - benchmark_rate) / benchmark_rate) * 100.0
            benchmark = {**benchmark, "comparison_mode": "market_premium_proxy"}
            return round(diff, 2), benchmark

        return 0.0, benchmark

    def _resolve_fresh(self, labor_category: str) -> dict[str, Any]:
        fallback = FALLBACK_RATE_BENCHMARKS.get(labor_category, FALLBACK_RATE_BENCHMARKS["General IT Services"])
        result: dict[str, Any] = {
            "labor_category": labor_category,
            "gsa_p50": fallback["p50"],
            "gsa_p75": fallback["p75"],
            "bls_hourly_median": None,
            "bls_burdened_median": None,
            "benchmark_rate": fallback["p50"],
            "source_mode": "fallback",
            "sample_size": 0,
        }

        if self.mode == "fallback":
            return result

        gsa = _fetch_gsa_calc_stats(labor_category)
        if gsa:
            result["gsa_p50"] = gsa.get("p50") or result["gsa_p50"]
            result["gsa_p75"] = gsa.get("p75") or result["gsa_p75"]
            result["sample_size"] = gsa.get("sample_size") or 0
            result["source_mode"] = "gsa"

        bls_hourly = _fetch_bls_hourly_median(labor_category)
        if bls_hourly:
            bls_burdened = bls_hourly * self.bls_burden_multiplier
            result["bls_hourly_median"] = round(bls_hourly, 2)
            result["bls_burdened_median"] = round(bls_burdened, 2)
            result["source_mode"] = "gsa+bls" if gsa else "bls"

        candidates = [
            value
            for value in (result.get("gsa_p50"), result.get("bls_burdened_median"))
            if isinstance(value, (int, float)) and value > 0
        ]
        if candidates:
            result["benchmark_rate"] = round(sum(candidates) / len(candidates), 2)

        return result


def search_awards_for_company(
    company: Company,
    fy_start: date,
    fy_end: date,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Query USASpending award search and return records expiring in FY window."""
    fields = [
        "Award ID",
        "Recipient Name",
        "Recipient UEI",
        "naics_code",
        "Awarding Agency",
        "Award Amount",
        "Description",
        "Type Set Aside",
        "Period of Performance End Date",
        "Period of Performance Current End Date",
    ]

    filters: dict[str, Any] = {
        "time_period": [{"start_date": EARLIEST_USASPENDING_DATE, "end_date": str(fy_end)}],
        "award_type_codes": CONTRACT_AWARD_TYPE_CODES,
    }
    if company.uei:
        filters["recipient_uei"] = [company.uei]
    else:
        filters["recipient_search_text"] = [company.name]

    selected: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        payload = {
            "fields": fields,
            "filters": filters,
            "page": page,
            "limit": 100,
            "sort": "Award ID",
            "order": "asc",
            "subawards": False,
        }
        body = _request_json("post", USASPENDING_ENDPOINT, payload=payload)
        if not body:
            logger.warning(
                "Skipping remaining USASpending pages for %s after repeated request failures.",
                company.name,
            )
            break

        results = body.get("results", [])
        for award in results:
            pop_end_raw = award.get("Period of Performance Current End Date") or award.get(
                "Period of Performance End Date"
            )
            pop_end = parse_date(pop_end_raw)
            if not pop_end:
                continue
            if fy_start <= pop_end <= fy_end:
                selected.append(award)

        metadata = body.get("page_metadata", {})
        if not metadata.get("hasNext"):
            break
    return selected


def build_recompete_rows(
    awards: list[dict[str, Any]],
    benchmark_resolver: RateBenchmarkResolver | None = None,
    fy_end: date | None = None,
    vendor_depth_provider: Callable[[str, str, date], dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Transform award payloads into ParaCharts rows and detail rows."""
    para_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []

    resolver = benchmark_resolver or RateBenchmarkResolver(mode="fallback", bls_burden_multiplier=2.0)
    end_date = fy_end or date.today()
    depth_provider = vendor_depth_provider or fetch_vendor_depth_signal

    for award in awards:
        agency = str(award.get("Awarding Agency") or "Unknown")
        award_amount = float(award.get("Award Amount") or 0.0)
        pop_end_raw = award.get("Period of Performance Current End Date") or award.get(
            "Period of Performance End Date"
        )
        pop_end = parse_date(pop_end_raw)
        if not pop_end:
            continue

        description = str(award.get("Description") or "")
        set_aside_text = str(award.get("Type Set Aside") or "Unknown")
        is_set_aside = is_small_business_set_aside(set_aside_text)
        labor_category = infer_labor_category(description)
        benchmark_diff, benchmark_meta = resolver.resolve(labor_category, description)
        naics_code = str(award.get("naics_code") or "").strip()
        rule_of_two_evidence = build_rule_of_two_evidence(
            is_set_aside=is_set_aside,
            naics_code=naics_code,
            awarding_agency=agency,
            fy_end=end_date,
            vendor_depth_provider=depth_provider,
        )

        para_rows.append(
            {
                "agency": agency,
                "value": award_amount,
                "expiry_quarter": quarter_from_date(pop_end),
                "set_aside_status": set_aside_text,
                "benchmark_diff": benchmark_diff,
                "rule_of_two_signal": rule_of_two_evidence["vendor_depth_signal"],
            }
        )

        detail_rows.append(
            {
                "award_id": award.get("Award ID"),
                "recipient_name": award.get("Recipient Name"),
                "recipient_uei": award.get("Recipient UEI"),
                "agency": agency,
                "award_amount": award_amount,
                "naics_code": naics_code,
                "period_of_performance_end_date": str(pop_end),
                "set_aside_status": set_aside_text,
                "rule_of_two_note": far_rule_of_two_note(is_set_aside),
                "rule_of_two_evidence": rule_of_two_evidence,
                "labor_category": labor_category,
                "benchmark_diff": benchmark_diff,
                "benchmark_meta": benchmark_meta,
            }
        )

    return para_rows, detail_rows


def write_summary_md(
    path: Path,
    companies: list[Company],
    fy_start: date,
    fy_end: date,
    para_rows: list[dict[str, Any]],
    detail_rows: list[dict[str, Any]],
) -> None:
    """Write a Markdown summary in repo reporting style."""
    by_agency: dict[str, int] = {}
    for row in para_rows:
        agency = str(row.get("agency") or "Unknown")
        by_agency[agency] = by_agency.get(agency, 0) + 1

    top_agencies = sorted(by_agency.items(), key=lambda item: item[1], reverse=True)[:10]
    set_aside_count = sum(1 for row in detail_rows if is_small_business_set_aside(row.get("set_aside_status")))
    high_confidence_rule_two = sum(
        1
        for row in detail_rows
        if ((row.get("rule_of_two_evidence") or {}).get("vendor_depth_signal") == "high")
    )

    lines = [
        "# Recompete Discovery Summary",
        "",
        f"- Cohort size: {len(companies)} companies",
        f"- FY window: {fy_start} to {fy_end}",
        f"- Expiring awards found: {len(detail_rows)}",
        f"- Small-business set-aside awards: {set_aside_count}",
        f"- Rule-of-Two high-confidence signals: {high_confidence_rule_two}",
        "- Data source: USASpending API (no SAM.gov key required)",
        "- FAR reference: 19.5 / 19.502-2 (Rule of Two)",
        "- Rate benchmark method: blended GSA CALC+ and BLS when available; fallback defaults otherwise",
        "",
        "## Top Agencies by Expiring Awards",
        "",
    ]

    if top_agencies:
        for agency, count in top_agencies:
            lines.append(f"- {agency}: {count}")
    else:
        lines.append("No awards found in selected period.")

    lines.extend(["", "## Sample Award Rows", ""])

    for row in detail_rows[:15]:
        lines.extend(
            [
                f"### {row.get('recipient_name', 'Unknown recipient')} | {row.get('award_id', 'Unknown award')}",
                "",
                f"- Agency: {row.get('agency', 'Unknown')}",
                f"- POP End: {row.get('period_of_performance_end_date', '')}",
                f"- Set-Aside: {row.get('set_aside_status', 'Unknown')}",
                f"- FAR 19.5 note: {row.get('rule_of_two_note', '')}",
                f"- Rule-of-Two signal: {(row.get('rule_of_two_evidence') or {}).get('vendor_depth_signal', 'unknown')}",
                f"- Rule-of-Two evidence: SB vendors={(row.get('rule_of_two_evidence') or {}).get('small_business_vendor_count_3y', 0)} / total={(row.get('rule_of_two_evidence') or {}).get('total_vendor_count_3y', 0)}",
                f"- Labor Category: {row.get('labor_category', 'General IT Services')}",
                f"- Benchmark diff: {row.get('benchmark_diff', 0.0)}%",
                f"- Benchmark source: {(row.get('benchmark_meta') or {}).get('source_mode', 'fallback')}",
                f"- Benchmark basis: {(row.get('benchmark_meta') or {}).get('comparison_mode', 'market_premium_proxy')}",
                "",
            ]
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def build_paracharts_specs(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build ParaCharts-compatible manifest specs from recompete rows."""
    agency_totals: dict[str, float] = {}
    quarter_counts: dict[str, int] = {"Q1": 0, "Q2": 0, "Q3": 0, "Q4": 0}
    set_aside_counts: dict[str, int] = {}
    benchmark_bands = {
        "Below -10%": 0,
        "-10% to +10%": 0,
        "+10% to +25%": 0,
        "Above +25%": 0,
    }
    rule_two_signal_counts: dict[str, int] = {
        "high": 0,
        "medium": 0,
        "low": 0,
        "insufficient": 0,
        "unknown": 0,
        "not-applicable": 0,
    }

    for row in rows:
        agency = str(row.get("agency") or "Unknown")
        value = float(row.get("value") or 0.0)
        quarter = str(row.get("expiry_quarter") or "Q1")
        set_aside = str(row.get("set_aside_status") or "Unknown")
        benchmark = float(row.get("benchmark_diff") or 0.0)
        rule_two_signal = str(row.get("rule_of_two_signal") or "unknown")

        agency_totals[agency] = agency_totals.get(agency, 0.0) + value
        if quarter in quarter_counts:
            quarter_counts[quarter] += 1
        else:
            quarter_counts[quarter] = quarter_counts.get(quarter, 0) + 1
        set_aside_counts[set_aside] = set_aside_counts.get(set_aside, 0) + 1
        rule_two_signal_counts[rule_two_signal] = rule_two_signal_counts.get(rule_two_signal, 0) + 1

        if benchmark < -10:
            benchmark_bands["Below -10%"] += 1
        elif benchmark <= 10:
            benchmark_bands["-10% to +10%"] += 1
        elif benchmark <= 25:
            benchmark_bands["+10% to +25%"] += 1
        else:
            benchmark_bands["Above +25%"] += 1

    top_agencies = sorted(agency_totals.items(), key=lambda item: item[1], reverse=True)[:15]
    top_set_asides = sorted(set_aside_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    quarter_order = ["Q1", "Q2", "Q3", "Q4"]

    manifests = [
        {
            "id": "agency-value-bar",
            "title": "Recompete Value by Agency",
            "description": "Total expiring award value by awarding agency.",
            "manifest": {
                "type": "bar",
                "series": [
                    {
                        "name": "Total Value",
                        "data": [round(amount, 2) for _, amount in top_agencies],
                    }
                ],
                "categories": [agency for agency, _ in top_agencies],
            },
        },
        {
            "id": "expiry-quarter-column",
            "title": "Expiry Quarter Distribution",
            "description": "Count of expiring awards by fiscal quarter.",
            "manifest": {
                "type": "column",
                "series": [
                    {
                        "name": "Expiring Awards",
                        "data": [quarter_counts.get(quarter, 0) for quarter in quarter_order],
                    }
                ],
                "categories": quarter_order,
            },
        },
        {
            "id": "set-aside-donut",
            "title": "Set-Aside Status Mix",
            "description": "Distribution of set-aside statuses in expiring awards.",
            "manifest": {
                "type": "donut",
                "series": [
                    {
                        "name": "Set-Aside Count",
                        "data": [count for _, count in top_set_asides],
                    }
                ],
                "categories": [status for status, _ in top_set_asides],
            },
        },
        {
            "id": "benchmark-diff-bar",
            "title": "Benchmark Difference Bands",
            "description": "Count of rows grouped by benchmark difference bands.",
            "manifest": {
                "type": "bar",
                "series": [
                    {
                        "name": "Rows",
                        "data": [benchmark_bands[key] for key in benchmark_bands],
                    }
                ],
                "categories": list(benchmark_bands.keys()),
            },
        },
        {
            "id": "rule-of-two-signal-bar",
            "title": "Rule-of-Two Evidence Signal",
            "description": "Signal strength from small-business vendor depth for Rule-of-Two screening.",
            "manifest": {
                "type": "bar",
                "series": [
                    {
                        "name": "Rows",
                        "data": [rule_two_signal_counts[key] for key in rule_two_signal_counts],
                    }
                ],
                "categories": list(rule_two_signal_counts.keys()),
            },
        },
    ]

    return {
        "version": "1.0",
        "source": "docs/data/recompetes.json",
        "row_count": len(rows),
        "manifests": manifests,
    }


def main() -> None:
    """Run recompete extraction and output JSON+Markdown artifacts."""
    args = parse_args()

    fy_start = date.fromisoformat(args.fy_start)
    fy_end = date.fromisoformat(args.fy_end)
    companies_file = resolve_companies_file(args.cohort, args.companies_file)
    companies = load_companies(companies_file)

    all_awards: list[dict[str, Any]] = []
    for company in companies:
        awards = search_awards_for_company(
            company=company,
            fy_start=fy_start,
            fy_end=fy_end,
            max_pages=args.max_pages_per_company,
        )
        all_awards.extend(awards)

    benchmark_resolver = RateBenchmarkResolver(
        mode=args.benchmark_mode,
        bls_burden_multiplier=args.bls_burden_multiplier,
    )
    para_rows, detail_rows = build_recompete_rows(
        all_awards,
        benchmark_resolver=benchmark_resolver,
        fy_end=fy_end,
    )

    output_json_path = Path(args.output_json)
    output_json_path.parent.mkdir(parents=True, exist_ok=True)
    output_json_path.write_text(json.dumps(para_rows, indent=2), encoding="utf-8")

    docs_output_path = Path(args.output_docs_json) if args.output_docs_json else None
    if docs_output_path:
        docs_output_path.parent.mkdir(parents=True, exist_ok=True)
        docs_output_path.write_text(json.dumps(para_rows, indent=2), encoding="utf-8")

    paracharts_output_path = Path(args.output_paracharts_spec) if args.output_paracharts_spec else None
    if paracharts_output_path:
        paracharts_output_path.parent.mkdir(parents=True, exist_ok=True)
        paracharts_specs = build_paracharts_specs(para_rows)
        paracharts_output_path.write_text(json.dumps(paracharts_specs, indent=2), encoding="utf-8")

    write_summary_md(
        path=Path(args.output_md),
        companies=companies,
        fy_start=fy_start,
        fy_end=fy_end,
        para_rows=para_rows,
        detail_rows=detail_rows,
    )

    print(f"Loaded {len(companies)} companies")
    print(f"Company source: {companies_file}")
    print(f"Benchmark mode: {args.benchmark_mode}")
    print(f"Found {len(detail_rows)} expiring awards in window")
    print(f"Wrote {output_json_path}")
    if docs_output_path:
        print(f"Wrote {docs_output_path}")
    if paracharts_output_path:
        print(f"Wrote {paracharts_output_path}")
    print(f"Wrote {Path(args.output_md)}")


if __name__ == "__main__":
    main()
