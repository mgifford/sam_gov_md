#!/usr/bin/env python3
"""Download and extract text from PDF and Word document attachments linked in SAM.gov opportunities."""

from __future__ import annotations

import argparse
import csv
import html as html_module
import io
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import docx
import pdfplumber
import requests

DEFAULT_CSV = "data/ContractOpportunitiesFullCSV.csv"
DEFAULT_OUTPUT_DIR = "docs/opportunities"
DEFAULT_LIMIT = 50
DEFAULT_TIMEOUT = 30

_DOCX_CONTENT_TYPES = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
)


def is_pdf_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith(".pdf")


def is_docx_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.path.lower().endswith((".docx", ".doc"))


def fetch_document_bytes(
    url: str, timeout: int = DEFAULT_TIMEOUT, retries: int = 2
) -> tuple[Optional[bytes], Optional[str]]:
    """Download a document from *url* and return ``(bytes, doc_type)``.

    *doc_type* is ``"pdf"`` or ``"docx"``.  Returns ``(None, None)`` when the
    resource cannot be fetched or is not a recognised document type.
    """
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
                return resp.content, "pdf"
            if any(ct in content_type for ct in _DOCX_CONTENT_TYPES) or is_docx_url(url):
                return resp.content, "docx"
            # Not a recognised document type
            return None, None
        except Exception as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None, None


def clean_document_text(text: str) -> str:
    """Normalize text extracted from documents: fix common encoding artifacts."""
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
            return clean_document_text(raw)
    except Exception as exc:
        return f"[PDF extraction error: {exc}]"


def extract_text_from_docx(docx_bytes: bytes) -> str:
    """Extract plain text from a Word document (.docx/.doc)."""
    try:
        document = docx.Document(io.BytesIO(docx_bytes))
        parts: list[str] = []
        for para in document.paragraphs:
            text = para.text.strip()
            if text:
                parts.append(text)
        # Extract text from tables (e.g. pricing or line-item tables)
        for table in document.tables:
            for row in table.rows:
                row_texts = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_texts:
                    parts.append(" | ".join(row_texts))
        raw = "\n\n".join(parts)
        return clean_document_text(raw)
    except Exception as exc:
        return f"[Word document extraction error: {exc}]"


def write_opportunity_pdf_content(
    notice_id: str,
    title: str,
    pdf_url: str,
    text: str,
    output_dir: Path,
    pdf_bytes: Optional[bytes] = None,
    save_pdf: bool = False,
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

    if save_pdf and pdf_bytes:
        # Derive a safe filename from the URL path, falling back to "attachment.pdf"
        url_path = urlparse(pdf_url).path
        raw_name = Path(url_path).name or "attachment"
        # Sanitize stem only (no dots) to prevent path-traversal via ".." sequences;
        # always use .pdf extension regardless of the original filename.
        raw_stem = Path(raw_name).stem
        safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", raw_stem) or "attachment"
        safe_name = f"{safe_stem}.pdf"
        (doc_dir / safe_name).write_bytes(pdf_bytes)


def write_opportunity_docx_content(
    notice_id: str,
    title: str,
    doc_url: str,
    text: str,
    output_dir: Path,
    doc_bytes: Optional[bytes] = None,
    save_doc: bool = False,
) -> None:
    """Write extracted Word document text to ``docx_content.md``."""
    doc_dir = output_dir / notice_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Word Document Content: {title}",
        "",
        f"- Notice ID: {notice_id}",
        f"- Document URL: {doc_url}",
        "",
        "## Extracted Text",
        "",
        text or "_No text could be extracted from this Word document._",
    ]
    (doc_dir / "docx_content.md").write_text("\n".join(lines), encoding="utf-8")

    if save_doc and doc_bytes:
        url_path = urlparse(doc_url).path
        raw_name = Path(url_path).name or "attachment"
        raw_stem = Path(raw_name).stem
        # Preserve the original extension (.docx or .doc) when saving the raw file
        url_suffix = Path(url_path).suffix.lower()
        safe_ext = url_suffix if url_suffix in (".docx", ".doc") else ".docx"
        safe_stem = re.sub(r"[^A-Za-z0-9_-]", "_", raw_stem) or "attachment"
        safe_name = f"{safe_stem}{safe_ext}"
        (doc_dir / safe_name).write_bytes(doc_bytes)


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
        description="Download and extract PDF and Word document attachments from SAM.gov opportunities"
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
        help=f"Output directory for extracted content (default: {DEFAULT_OUTPUT_DIR})",
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
    parser.add_argument(
        "--save-pdf",
        action="store_true",
        help=(
            "Save the raw attachment file alongside the extracted markdown "
            "in the opportunity directory (applies to both PDFs and Word documents)"
        ),
    )
    parser.add_argument(
        "--max-file-size",
        type=int,
        default=50 * 1024 * 1024,  # 50 MB
        help="Maximum attachment file size in bytes to save (default: 52428800 = 50 MB)",
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
        doc_url = (row.get("AdditionalInfoLink") or "").strip()

        if not notice_id or not doc_url:
            skipped += 1
            continue

        print(f"  [{i}/{len(candidates)}] {notice_id}: {doc_url[:80]}")

        doc_bytes, doc_type = fetch_document_bytes(doc_url, timeout=args.timeout)
        if doc_bytes is None:
            print(f"    Skipped (not a PDF/Word document or download failed)")
            skipped += 1
            summary_records.append(
                {"notice_id": notice_id, "url": doc_url, "status": "skipped"}
            )
            continue

        # Enforce max file size limit when saving to avoid large repo blobs
        doc_too_large = args.save_pdf and len(doc_bytes) > args.max_file_size

        try:
            if doc_type == "docx":
                text = extract_text_from_docx(doc_bytes)
                write_opportunity_docx_content(
                    notice_id,
                    title,
                    doc_url,
                    text,
                    output_dir,
                    doc_bytes=doc_bytes if not doc_too_large else None,
                    save_doc=args.save_pdf,
                )
                type_label = "Word document"
            else:
                text = extract_text_from_pdf(doc_bytes)
                write_opportunity_pdf_content(
                    notice_id,
                    title,
                    doc_url,
                    text,
                    output_dir,
                    pdf_bytes=doc_bytes if not doc_too_large else None,
                    save_pdf=args.save_pdf,
                )
                type_label = "PDF"

            word_count = len(text.split()) if text else 0
            size_kb = len(doc_bytes) // 1024
            saved_file = args.save_pdf and not doc_too_large
            if doc_too_large:
                print(
                    f"    Extracted ~{word_count} words from {type_label} "
                    f"({size_kb} KB exceeds size limit; not saved)"
                )
            else:
                print(
                    f"    Extracted ~{word_count} words from {type_label}"
                    + (f", saved file ({size_kb} KB)" if saved_file else "")
                )
            extracted += 1
            summary_records.append({
                "notice_id": notice_id,
                "url": doc_url,
                "status": "ok",
                "doc_type": doc_type,
                "words": word_count,
                "file_saved": saved_file,
                "size_bytes": len(doc_bytes),
            })
        except Exception as exc:
            print(f"    Error processing {doc_type or 'document'}: {exc}")
            errors += 1
            summary_records.append(
                {"notice_id": notice_id, "url": doc_url, "status": "error", "error": str(exc)}
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

    print(f"\nExtraction complete: {extracted} extracted, {skipped} skipped, {errors} errors")
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()
