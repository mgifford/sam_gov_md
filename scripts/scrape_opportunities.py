#!/usr/bin/env python3
"""Download and extract text from PDF attachments linked in SAM.gov opportunities."""

from __future__ import annotations

import argparse
import csv
import html as html_module
import io
import json
import os
import time
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import pdfplumber
import requests

DEFAULT_CSV = "data/ContractOpportunitiesFullCSV.csv"
DEFAULT_OUTPUT_DIR = "docs/opportunities"
DEFAULT_LIMIT = 50
DEFAULT_TIMEOUT = 30


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


def fetch_pdf_bytes(url: str, timeout: int = DEFAULT_TIMEOUT, retries: int = 2) -> Optional[bytes]:
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                timeout=timeout,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SAMGovBot/1.0)"},
                allow_redirects=True,
            )
            resp.raise_for_status()
            content_type = resp.headers.get("Content-Type", "").lower()
            if "pdf" in content_type or is_pdf_url(url):
                return resp.content
            # Not a PDF response
            return None
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def clean_pdf_text(text: str) -> str:
    """Normalize text extracted from PDFs: fix common encoding artifacts."""
    if not text:
        return text
    # Unescape any HTML entities that may appear in the source
    text = html_module.unescape(text)
    # Normalize Unicode to NFC (composed form) to consolidate combining chars
    text = unicodedata.normalize("NFC", text)
    return text


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            pages: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text)
            raw = "\n\n".join(pages)
            return clean_pdf_text(raw)
    except Exception as exc:
        return f"[PDF extraction error: {exc}]"


def write_opportunity_pdf_content(
    notice_id: str,
    title: str,
    pdf_url: str,
    text: str,
    output_dir: Path,
) -> None:
    doc_dir = output_dir / notice_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# PDF Content: {title}",
        "",
        f"- Notice ID: {notice_id}",
        f"- PDF URL: {pdf_url}",
        "",
        "## Extracted Text",
        "",
        text or "_No text could be extracted from this PDF._",
    ]
    (doc_dir / "pdf_content.md").write_text("\n".join(lines), encoding="utf-8")


def load_csv(csv_path: str) -> list[dict]:
    rows: list[dict] = []
    try:
        # SAM.gov CSVs commonly use Windows-1252 encoding; errors="replace" handles any
        # remaining invalid bytes without crashing on unusual field values.
        with open(csv_path, "r", encoding="windows-1252", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception as exc:
        print(f"Error reading CSV {csv_path}: {exc}")
    return rows


def select_candidates(rows: list[dict], limit: int) -> list[dict]:
    """Select top candidates that have a non-empty AdditionalInfoLink."""
    with_links = [
        row for row in rows
        if (row.get("AdditionalInfoLink") or "").strip()
    ]
    # Sort by posted date descending (most recent first)
    with_links.sort(key=lambda r: (r.get("PostedDate") or ""), reverse=True)
    return with_links[:limit]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download and extract PDF attachments from SAM.gov opportunities"
    )
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help=f"Path to the full CSV extract (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Max number of opportunities to process (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for extracted PDF content (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--summary-output",
        default="data/today/pdf_extraction_summary.json",
        help="Path to write extraction summary JSON",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading CSV from {args.csv}")
    rows = load_csv(args.csv)
    if not rows:
        print("No rows loaded from CSV. Exiting.")
        return

    print(f"Total rows in CSV: {len(rows)}")
    candidates = select_candidates(rows, args.limit)
    print(f"Candidates with AdditionalInfoLink: {len(candidates)}")

    extracted = 0
    skipped = 0
    errors = 0
    summary_records: list[dict] = []

    for i, row in enumerate(candidates, start=1):
        notice_id = (row.get("NoticeId") or "").strip()
        title = (row.get("Title") or "Untitled").strip()
        pdf_url = (row.get("AdditionalInfoLink") or "").strip()

        if not notice_id or not pdf_url:
            skipped += 1
            continue

        print(f"  [{i}/{len(candidates)}] {notice_id}: {pdf_url[:80]}")

        pdf_bytes = fetch_pdf_bytes(pdf_url, timeout=args.timeout)
        if pdf_bytes is None:
            print(f"    Skipped (not a PDF or download failed)")
            skipped += 1
            summary_records.append(
                {"notice_id": notice_id, "url": pdf_url, "status": "skipped"}
            )
            continue

        try:
            text = extract_text_from_pdf(pdf_bytes)
            write_opportunity_pdf_content(notice_id, title, pdf_url, text, output_dir)
            word_count = len(text.split()) if text else 0
            print(f"    Extracted ~{word_count} words")
            extracted += 1
            summary_records.append(
                {"notice_id": notice_id, "url": pdf_url, "status": "ok", "words": word_count}
            )
        except Exception as exc:
            print(f"    Error processing PDF: {exc}")
            errors += 1
            summary_records.append(
                {"notice_id": notice_id, "url": pdf_url, "status": "error", "error": str(exc)}
            )

    summary = {
        "csv": args.csv,
        "limit": args.limit,
        "total_rows": len(rows),
        "candidates": len(candidates),
        "extracted": extracted,
        "skipped": skipped,
        "errors": errors,
        "records": summary_records,
    }

    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\nPDF extraction complete: {extracted} extracted, {skipped} skipped, {errors} errors")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
