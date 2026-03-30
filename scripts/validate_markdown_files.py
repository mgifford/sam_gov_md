#!/usr/bin/env python3
"""Validate that all markdown files referenced in the dashboard actually exist."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def validate_markdown_files(docs_dir: Path) -> None:
    """Check if all markdown files exist and have content."""
    records_file = docs_dir / "data" / "today_records.json"

    if not records_file.exists():
        print(f"Error: {records_file} not found")
        return

    with records_file.open(encoding="utf-8") as f:
        records = json.load(f)

    # Check each record's markdown file
    missing: list[str] = []
    empty: list[str] = []
    valid: list[str] = []

    for record in records:
        notice_id = record.get("NoticeId", "").strip()
        if not notice_id:
            continue

        md_file = docs_dir / "opportunities" / notice_id / "index.md"

        if not md_file.exists():
            missing.append(notice_id)
        else:
            content = md_file.read_text(encoding="utf-8").strip()
            if not content:
                empty.append(notice_id)
            else:
                valid.append(notice_id)

    # Report
    print("\n📊 Markdown File Validation Report")
    print("=" * 50)
    print(f"Total records: {len(records)}")
    print(f"✅ Valid markdown files: {len(valid)}")
    print(f"⚠️  Missing markdown files: {len(missing)}")
    print(f"❌ Empty markdown files: {len(empty)}")

    if missing:
        print("\nFirst 10 missing markdown files:")
        for notice_id in missing[:10]:
            print(f"  - {notice_id}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    if empty:
        print("\nEmpty markdown files:")
        for notice_id in empty:
            print(f"  - {notice_id}")

    # Suggestions
    if missing or empty:
        print("\n💡 Suggestions:")
        print("  1. Run: python scripts/process_today.py --target-date YYYY-MM-DD --fallback-latest")
        print("  2. Verify all files were written to docs/opportunities/*/index.md")
        print("  3. Check GitHub Pages workflow (Actions tab) to ensure Jekyll build succeeded")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate markdown files referenced in the dashboard"
    )
    parser.add_argument("--docs-dir", default="docs", help="Path to the docs directory")
    args = parser.parse_args()

    validate_markdown_files(Path(args.docs_dir))


if __name__ == "__main__":
    main()
