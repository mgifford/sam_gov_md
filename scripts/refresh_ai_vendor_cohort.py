#!/usr/bin/env python3
"""Refresh the federal AI vendor cohort from USASpending search results."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Callable

import requests

USASPENDING_ENDPOINT = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
REQUEST_TIMEOUT = 30
DEFAULT_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "generative ai",
    "large language model",
]


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Refresh AI vendor cohort list")
    parser.add_argument("--start-date", default="2023-10-01", help="Query start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=str(date.today()), help="Query end date (YYYY-MM-DD)")
    parser.add_argument("--keywords", default="|".join(DEFAULT_KEYWORDS), help="Pipe-delimited keywords")
    parser.add_argument("--max-pages", type=int, default=8, help="Maximum pages to scan")
    parser.add_argument("--page-size", type=int, default=100, help="Rows per page")
    parser.add_argument("--top-n", type=int, default=30, help="Top vendors to keep")
    parser.add_argument(
        "--output",
        default="config/company_lists/ai_vendors_federal.json",
        help="Output cohort file path",
    )
    return parser.parse_args()


def parse_keywords(raw: str) -> list[str]:
    """Parse pipe-delimited keyword string into normalized list."""
    return [part.strip() for part in raw.split("|") if part.strip()]


def fetch_vendor_candidates(
    start_date: str,
    end_date: str,
    keywords: list[str],
    max_pages: int,
    page_size: int,
    post_fn: Callable[..., Any] = requests.post,
) -> list[dict[str, Any]]:
    """Fetch and rank vendor candidates from USASpending award search."""
    fields = ["Recipient Name", "Recipient UEI", "Award Amount"]
    filters: dict[str, Any] = {
        "time_period": [{"start_date": start_date, "end_date": end_date}],
        "award_type_codes": ["A", "B", "C", "D"],
        "keywords": keywords,
    }

    by_vendor: dict[str, dict[str, Any]] = {}
    for page in range(1, max_pages + 1):
        payload = {
            "fields": fields,
            "filters": filters,
            "page": page,
            "limit": page_size,
            "sort": "Award Amount",
            "order": "desc",
            "subawards": False,
        }
        response = post_fn(USASPENDING_ENDPOINT, json=payload, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        body = response.json()

        for row in body.get("results", []):
            name = str(row.get("Recipient Name") or "").strip()
            if not name:
                continue
            key = name.upper()
            amount = float(row.get("Award Amount") or 0.0)
            uei = str(row.get("Recipient UEI") or "").strip()
            current = by_vendor.get(key)
            if current is None or amount > current["award_amount"]:
                by_vendor[key] = {"name": name, "uei": uei, "award_amount": amount}

        if not body.get("page_metadata", {}).get("hasNext"):
            break

    return sorted(by_vendor.values(), key=lambda item: item["award_amount"], reverse=True)


def write_company_cohort(path: Path, vendors: list[dict[str, Any]], top_n: int) -> None:
    """Write top vendors to the standard company-list JSON shape."""
    cohort = [{"name": row["name"], "uei": row["uei"]} for row in vendors[:top_n]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cohort, indent=2), encoding="utf-8")


def main() -> None:
    """Refresh AI cohort file from the latest USASpending results."""
    args = parse_args()
    keywords = parse_keywords(args.keywords)
    vendors = fetch_vendor_candidates(
        start_date=args.start_date,
        end_date=args.end_date,
        keywords=keywords,
        max_pages=args.max_pages,
        page_size=args.page_size,
    )
    output = Path(args.output)
    write_company_cohort(output, vendors, args.top_n)

    print(f"Keywords: {', '.join(keywords)}")
    print(f"Vendors found: {len(vendors)}")
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
