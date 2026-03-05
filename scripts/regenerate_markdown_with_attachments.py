#!/usr/bin/env python3
"""Regenerate markdown opportunity pages with attachment metadata."""

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


def parse_date(value: str) -> date | None:
    value = (value or "").strip()
    if not value:
        return None
    value = value[:10]
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def extract_attachments(description: str) -> dict[str, Any]:
    """Extract attachment filenames and count from description text."""
    if not description:
        return {"count": 0, "attachments": []}
    
    attachments: list[str] = []
    
    # Pattern 1: "Attachment N: Filename" or "Attachment (N): Filename"
    attachment_pattern = r'(?:attachment|exhibit|annex|appendix)\s+(?:\()?[a-z0-9]+(?:\))?\s*:?\s*([^\n]+?)(?=\n|$)'
    matches = re.findall(attachment_pattern, description, re.IGNORECASE)
    for match in matches:
        filename = match.strip()
        # Clean up common artifacts
        filename = re.sub(r'["""\']', '"', filename)
        filename = filename.rstrip('.,;')
        if filename and len(filename) > 2:
            if filename not in attachments:
                attachments.append(filename)
    
    # Pattern 2: Direct file references like "Att 1_FAR 52.204-24 Nov 2021.pdf"
    file_pattern = r'([Aa]tt\s+\d+_[^\n]+\.(?:pdf|docx?|xlsx?|pptx?|txt))'
    file_matches = re.findall(file_pattern, description)
    for match in file_matches:
        if match not in attachments:
            attachments.append(match)
    
    return {
        "count": len(attachments),
        "attachments": attachments
    }


def write_markdown_opportunity(row: dict, output_dir: Path) -> bool:
    """Write a single opportunity markdown page."""
    notice_id = (row.get("NoticeId") or "").strip()
    if not notice_id:
        return False

    doc_dir = output_dir / "opportunities" / notice_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    title = (row.get("Title") or "Untitled Opportunity").strip()
    agency = (row.get("Department/Ind.Agency") or "Unknown Agency").strip()
    notice_type = (row.get("Type") or "Unknown Type").strip()
    posted = (row.get("PostedDate") or "").strip()
    sol_number = (row.get("Sol#") or "").strip()
    description = (row.get("Description") or "").strip()
    sam_link = (row.get("Link") or "").strip()
    pdf_link = (row.get("AdditionalInfoLink") or "").strip()
    awardee = (row.get("Awardee") or "").strip()
    award_amount = (row.get("Award$") or "").strip()
    primary_contact_name = (row.get("PrimaryContactFullname") or "").strip()
    primary_contact_title = (row.get("PrimaryContactTitle") or "").strip()
    primary_contact_email = (row.get("PrimaryContactEmail") or "").strip()
    primary_contact_phone = (row.get("PrimaryContactPhone") or "").strip()
    secondary_contact_name = (row.get("SecondaryContactFullname") or "").strip()
    secondary_contact_title = (row.get("SecondaryContactTitle") or "").strip()
    secondary_contact_email = (row.get("SecondaryContactEmail") or "").strip()
    secondary_contact_phone = (row.get("SecondaryContactPhone") or "").strip()
    
    # Extract attachment information
    attachment_info = extract_attachments(description)

    # Create Jekyll front matter
    markdown_lines = [
        "---",
        f"layout: default",
        f"title: {title}",
        f"agency: {agency}",
        f"notice_type: {notice_type}",
        f"notice_id: {notice_id}",
        "---",
        "",
        f"# {title}",
        "",
        f"- Agency: {agency}",
        f"- Type: {notice_type}",
        f"- Posted: {posted}",
    ]
    if sol_number:
        markdown_lines.append(f"- Solicitation Number: {sol_number}")
    if awardee:
        markdown_lines.append(f"- Awardee: {awardee}")
    if award_amount:
        markdown_lines.append(f"- Award Amount: {award_amount}")

    markdown_lines.extend(["", "## Summary", "", description or "No summary provided."])

    if any(
        [
            primary_contact_name,
            primary_contact_title,
            primary_contact_email,
            primary_contact_phone,
            secondary_contact_name,
            secondary_contact_title,
            secondary_contact_email,
            secondary_contact_phone,
        ]
    ):
        markdown_lines.extend(["", "## Contacts", ""])
        if primary_contact_name or primary_contact_title or primary_contact_email or primary_contact_phone:
            markdown_lines.append("- Primary Contact:")
            if primary_contact_name:
                markdown_lines.append(f"  - Name: {primary_contact_name}")
            if primary_contact_title:
                markdown_lines.append(f"  - Title: {primary_contact_title}")
            if primary_contact_email:
                markdown_lines.append(f"  - Email: {primary_contact_email}")
            if primary_contact_phone:
                markdown_lines.append(f"  - Phone: {primary_contact_phone}")
        if secondary_contact_name or secondary_contact_title or secondary_contact_email or secondary_contact_phone:
            markdown_lines.append("- Secondary Contact:")
            if secondary_contact_name:
                markdown_lines.append(f"  - Name: {secondary_contact_name}")
            if secondary_contact_title:
                markdown_lines.append(f"  - Title: {secondary_contact_title}")
            if secondary_contact_email:
                markdown_lines.append(f"  - Email: {secondary_contact_email}")
            if secondary_contact_phone:
                markdown_lines.append(f"  - Phone: {secondary_contact_phone}")
    
    # Add Attachments section if any exist
    if attachment_info["count"] > 0:
        markdown_lines.extend(["", "## Attachments", ""])
        markdown_lines.append(f"**Total: {attachment_info['count']} attachment(s)**")
        markdown_lines.append("")
        for i, attachment in enumerate(attachment_info["attachments"], 1):
            markdown_lines.append(f"- Attachment {i}: {attachment}")
    
    markdown_lines.extend(["", "## Links", ""])
    if sam_link:
        markdown_lines.append(f"- SAM.gov: {sam_link}")
    if pdf_link:
        markdown_lines.append(f"- PDF / Additional Info: {pdf_link}")

    (doc_dir / "index.md").write_text("\n".join(markdown_lines), encoding="utf-8")
    return True


def main():
    records_file = Path("data/today/records.json")
    output_dir = Path("docs")
    
    if not records_file.exists():
        print(f"Error: {records_file} not found")
        return
    
    with open(records_file, "r", encoding="utf-8") as f:
        records = json.load(f)
    
    written = 0
    for i, record in enumerate(records):
        if write_markdown_opportunity(record, output_dir):
            written += 1
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{len(records)} records processed...")
    
    print(f"\nMarkdown documents written: {written}")
    
    # Count records with attachments
    with_attachments = sum(1 for r in records if extract_attachments(r.get("Description", ""))["count"] > 0)
    print(f"Records with attachments: {with_attachments} ({100*with_attachments/len(records):.1f}%)")


if __name__ == "__main__":
    main()
