#!/usr/bin/env python3
"""Regenerate markdown opportunity pages with attachment metadata."""

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


def parse_date(value: str) -> date | None:
    """Parse a date string in YYYY-MM-DD or MM/DD/YYYY format.

    Args:
        value: Raw date string from SAM.gov data.

    Returns:
        A :class:`datetime.date` on success, or ``None`` if the value is
        empty or cannot be parsed.
    """
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
    attachment_pattern = (
        r"(?:attachment|exhibit|annex|appendix)"
        r"\s+(?:\()?[a-z0-9]+(?:\))?\s*:?\s*([^\n]+?)(?=\n|$)"
    )
    matches = re.findall(attachment_pattern, description, re.IGNORECASE)
    for match in matches:
        filename = match.strip()
        # Clean up common artifacts
        filename = re.sub(r'["""\']', '"', filename)
        filename = filename.rstrip(".,;")
        if filename and len(filename) > 2:
            if filename not in attachments:
                attachments.append(filename)

    # Pattern 2: Direct file references like "Att 1_FAR 52.204-24 Nov 2021.pdf"
    file_pattern = r"([Aa]tt\s+\d+_[^\n]+\.(?:pdf|docx?|xlsx?|pptx?|txt))"
    file_matches = re.findall(file_pattern, description)
    for match in file_matches:
        if match not in attachments:
            attachments.append(match)

    return {"count": len(attachments), "attachments": attachments}


def _extract_row_fields(row: dict) -> dict[str, str]:
    """Return a flat dict of normalised field values from a CSV row.

    Args:
        row: Raw CSV row dictionary from SAM.gov data.

    Returns:
        Dictionary of cleaned field values ready for markdown rendering.
    """
    def get(key: str, default: str = "") -> str:
        """Return the stripped row value for ``key``, or ``default``."""
        return (row.get(key) or default).strip()

    return {
        "title": get("Title", "Untitled Opportunity"),
        "agency": get("Department/Ind.Agency", "Unknown Agency"),
        "notice_type": get("Type", "Unknown Type"),
        "notice_id": get("NoticeId"),
        "posted": get("PostedDate"),
        "sol_number": get("Sol#"),
        "description": get("Description"),
        "sam_link": get("Link"),
        "pdf_link": get("AdditionalInfoLink"),
        "awardee": get("Awardee"),
        "award_amount": get("Award$"),
        "primary_contact_name": get("PrimaryContactFullname"),
        "primary_contact_title": get("PrimaryContactTitle"),
        "primary_contact_email": get("PrimaryContactEmail"),
        "primary_contact_phone": get("PrimaryContactPhone"),
        "secondary_contact_name": get("SecondaryContactFullname"),
        "secondary_contact_title": get("SecondaryContactTitle"),
        "secondary_contact_email": get("SecondaryContactEmail"),
        "secondary_contact_phone": get("SecondaryContactPhone"),
    }


def _build_front_matter(fields: dict[str, str]) -> list[str]:
    """Build Jekyll YAML front matter lines for an opportunity page.

    Args:
        fields: Normalised field values from :func:`_extract_row_fields`.

    Returns:
        List of markdown lines including the opening and closing ``---``
        fences.
    """
    lines = [
        "---",
        "layout: default",
        f"title: {fields['title']}",
        f"agency: {fields['agency']}",
        f"notice_type: {fields['notice_type']}",
        f"notice_id: {fields['notice_id']}",
        "---",
        "",
        f"# {fields['title']}",
        "",
        f"- Agency: {fields['agency']}",
        f"- Type: {fields['notice_type']}",
        f"- Posted: {fields['posted']}",
    ]
    if fields["sol_number"]:
        lines.append(f"- Solicitation Number: {fields['sol_number']}")
    if fields["awardee"]:
        lines.append(f"- Awardee: {fields['awardee']}")
    if fields["award_amount"]:
        lines.append(f"- Award Amount: {fields['award_amount']}")
    return lines


def _build_contact_block(label: str, contact: dict[str, str]) -> list[str]:
    """Build a markdown list block for a single contact entry.

    Args:
        label: Display label, e.g. ``"Primary Contact"``.
        contact: Mapping of field names (``name``, ``title``, ``email``,
            ``phone``) to their values.

    Returns:
        List of indented markdown lines, or an empty list when all fields
        are blank.
    """
    if not any(contact.values()):
        return []
    lines = [f"- {label}:"]
    for key, prefix in (
        ("name", "Name"),
        ("title", "Title"),
        ("email", "Email"),
        ("phone", "Phone"),
    ):
        if contact.get(key):
            lines.append(f"  - {prefix}: {contact[key]}")
    return lines


def _build_contacts_section(fields: dict[str, str]) -> list[str]:
    """Build the Contacts markdown section from normalised row fields.

    Args:
        fields: Normalised field values from :func:`_extract_row_fields`.

    Returns:
        List of markdown lines for the Contacts section, or an empty list
        when no contact information is present.
    """
    primary = {
        "name": fields["primary_contact_name"],
        "title": fields["primary_contact_title"],
        "email": fields["primary_contact_email"],
        "phone": fields["primary_contact_phone"],
    }
    secondary = {
        "name": fields["secondary_contact_name"],
        "title": fields["secondary_contact_title"],
        "email": fields["secondary_contact_email"],
        "phone": fields["secondary_contact_phone"],
    }
    if not any(primary.values()) and not any(secondary.values()):
        return []
    lines: list[str] = ["", "## Contacts", ""]
    lines.extend(_build_contact_block("Primary Contact", primary))
    lines.extend(_build_contact_block("Secondary Contact", secondary))
    return lines


def _build_links_section(sam_link: str, pdf_link: str) -> list[str]:
    """Build the Links markdown section.

    Args:
        sam_link: URL for the SAM.gov opportunity page.
        pdf_link: URL for an additional information document or PDF.

    Returns:
        List of markdown lines for the Links section.
    """
    lines: list[str] = ["", "## Links", ""]
    if sam_link:
        lines.append(f"- [SAM.gov opportunity page]({sam_link})")
    if pdf_link:
        if pdf_link.lower().endswith(".pdf"):
            lines.append(f"- [PDF Attachment]({pdf_link})")
        else:
            lines.append(f"- [Additional Information]({pdf_link})")
    if not sam_link and not pdf_link:
        lines.append("_No links are available for this opportunity._")
    return lines


def write_markdown_opportunity(row: dict, output_dir: Path) -> bool:
    """Write a single opportunity's markdown page to disk.

    Builds a Jekyll-compatible ``index.md`` under
    ``<output_dir>/opportunities/<notice_id>/`` from the supplied CSV row.

    Args:
        row: Raw CSV row dictionary from SAM.gov data.
        output_dir: Root directory for generated documentation
            (e.g. ``docs/``).

    Returns:
        ``True`` if the file was written, ``False`` when the row has no
        ``NoticeId`` and is therefore skipped.
    """
    fields = _extract_row_fields(row)
    if not fields["notice_id"]:
        return False

    doc_dir = output_dir / "opportunities" / fields["notice_id"]
    doc_dir.mkdir(parents=True, exist_ok=True)

    markdown_lines = _build_front_matter(fields)
    markdown_lines.extend(
        ["", "## Summary", "", fields["description"] or "No summary provided."]
    )
    markdown_lines.extend(_build_contacts_section(fields))

    attachment_info = extract_attachments(fields["description"])
    if attachment_info["count"] > 0:
        count = attachment_info["count"]
        markdown_lines.extend(["", "## Attachments", ""])
        markdown_lines.append(f"**Total: {count} attachment(s)**")
        markdown_lines.append("")
        for i, attachment in enumerate(attachment_info["attachments"], 1):
            markdown_lines.append(f"- Attachment {i}: {attachment}")

    markdown_lines.extend(
        _build_links_section(fields["sam_link"], fields["pdf_link"])
    )

    (doc_dir / "index.md").write_text(
        "\n".join(markdown_lines), encoding="utf-8"
    )
    return True


def main() -> None:
    """Read records from ``data/today/records.json`` and write markdown pages.

    Iterates over every record in the daily JSON file produced by
    ``process_today.py`` and calls :func:`write_markdown_opportunity` for
    each one.  Progress is printed every 100 records, and a final summary
    reports how many pages were written and how many contained attachments.
    """
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

    with_attachments = sum(
        1
        for r in records
        if extract_attachments(r.get("Description", ""))["count"] > 0
    )
    pct = 100 * with_attachments / len(records) if records else 0.0
    print(f"Records with attachments: {with_attachments} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
