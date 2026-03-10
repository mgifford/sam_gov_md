#!/usr/bin/env python3
"""Process SAM.gov Contract Opportunities for a target date and generate web-ready outputs."""

from __future__ import annotations

import argparse
import csv
import html as html_module
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import requests
import yaml

from ollama_analyzer import GitHubModelsClient, OllamaClient, analyze_record

DEFAULT_CSV_URL = (
    "https://s3.amazonaws.com/falextracts/Contract Opportunities/datagov/"
    "ContractOpportunitiesFullCSV.csv"
)


@dataclass
class TermDef:
    name: str
    category: str
    patterns: list[str]


def normalize_date(posted_date: str) -> str:
    posted_date = (posted_date or "").strip()
    if not posted_date:
        return ""
    return posted_date[:10]


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


def _decode_csv_line(line_bytes: bytes) -> str:
    """Decode a CSV line, falling back to windows-1252 if UTF-8 fails."""
    try:
        return line_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return line_bytes.decode("windows-1252", "replace")


def clean_description(text: str) -> str:
    """Unescape HTML entities and add paragraph breaks at numbered sections."""
    if not text:
        return text
    # Unescape HTML entities (e.g. &amp; → &, &lt; → <, &#x2019; → ')
    text = html_module.unescape(text)
    # Insert a blank line before top-level numbered sections like "1.0 Title" or "2.0 Title"
    text = re.sub(r'(?<!\n)\s+(?=\d+\.\d+ [A-Z])', r'\n\n', text)
    return text


def is_win(row: dict[str, str]) -> bool:
    notice_type = (row.get("Type") or "").lower()
    return "award" in notice_type or "win" in notice_type


def extract_attachments(description: str) -> dict[str, Any]:
    """Extract attachment filenames and count from description text.
    
    Looks for patterns like:
    - Attachment 1: filename.pdf
    - Exhibit A: filename.pdf
    - Annex I: filename.pdf
    - Appendix A: filename.pdf
    """
    if not description:
        return {"count": 0, "attachments": []}
    
    attachments: list[str] = []
    
    # Pattern 1: "Attachment N: Filename" or "Attachment (N): Filename"
    attachment_pattern = r'(?:attachment|exhibit|annex|appendix)\s+(?:\()?[a-z0-9]+(?:\))?\s*:?\s*([^\n]+?)(?=\n|$)'
    matches = re.findall(attachment_pattern, description, re.IGNORECASE)
    for match in matches:
        filename = match.strip()
        # Clean up common artifacts
        filename = re.sub(r'["""\']', '"', filename)  # Normalize quotes
        filename = filename.rstrip('.,;')
        if filename and len(filename) > 2:  # Avoid single characters
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


def load_terms(path: Path) -> list[TermDef]:
    with path.open("r", encoding="utf-8") as f:
        payload = yaml.safe_load(f)
    terms_raw = payload.get("terms", [])
    terms: list[TermDef] = []
    for item in terms_raw:
        terms.append(
            TermDef(
                name=item.get("name", ""),
                category=item.get("category", "other"),
                patterns=item.get("patterns", []),
            )
        )
    return terms


def scan_terms(text: str, terms: list[TermDef]) -> tuple[Counter, dict[str, list[dict[str, int]]]]:
    term_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    matched_terms: list[dict[str, int]] = []
    for term in terms:
        count = 0
        for pattern in term.patterns:
            count += len(re.findall(pattern, text, flags=re.IGNORECASE))
        if count > 0:
            term_counts[term.name] += count
            category_counts[term.category] += count
            matched_terms.append(
                {"term": term.name, "category": term.category, "count": count}
            )
    matched_terms.sort(key=lambda x: x["count"], reverse=True)
    return term_counts, {"categories": category_counts, "terms": matched_terms}


def to_relationships(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    edges: Counter[tuple[str, str, str]] = Counter()
    nodes: dict[str, str] = {}

    for row in records:
        agency = (row.get("Department/Ind.Agency") or "Unknown Agency").strip()
        notice_type = (row.get("Type") or "Unknown Type").strip()
        naics = (row.get("NaicsCode") or "Unknown NAICS").strip()

        agency_node = f"agency:{agency}"
        type_node = f"type:{notice_type}"
        naics_node = f"naics:{naics}"

        nodes[agency_node] = agency
        nodes[type_node] = notice_type
        nodes[naics_node] = naics

        edges[(agency_node, type_node, "agency_to_type")] += 1
        edges[(type_node, naics_node, "type_to_naics")] += 1

    return {
        "nodes": [
            {"id": node_id, "label": label, "group": node_id.split(":", 1)[0]}
            for node_id, label in nodes.items()
        ],
        "edges": [
            {"source": src, "target": dst, "kind": kind, "weight": weight}
            for (src, dst, kind), weight in edges.items()
        ],
    }


def build_department_breakdown(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_agency: dict[str, dict[str, int]] = {}
    for row in records:
        agency = (row.get("Department/Ind.Agency") or "Unknown Agency").strip()
        bucket = by_agency.setdefault(
            agency,
            {"department": agency, "total": 0, "opportunities": 0, "wins": 0},
        )
        bucket["total"] += 1
        if is_win(row):
            bucket["wins"] += 1
        else:
            bucket["opportunities"] += 1
    return sorted(by_agency.values(), key=lambda item: item["total"], reverse=True)


def build_date_breakdown(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, int]] = {}
    for row in records:
        posted_date = normalize_date(row.get("PostedDate", ""))
        if not posted_date:
            continue
        bucket = by_date.setdefault(
            posted_date,
            {"date": posted_date, "total": 0, "opportunities": 0, "awarded": 0},
        )
        bucket["total"] += 1
        if is_win(row):
            bucket["awarded"] += 1
        else:
            bucket["opportunities"] += 1
    return sorted(by_date.values(), key=lambda item: item["date"], reverse=True)


def build_award_company_history(all_rows: list[dict[str, Any]]) -> dict[str, Any]:
    awardee_counts: Counter[str] = Counter()
    by_month: dict[str, dict[str, Any]] = {}

    for row in all_rows:
        if not is_win(row):
            continue
        awardee = (row.get("Awardee") or "").strip()
        if not awardee:
            continue
        awardee_counts[awardee] += 1

        award_dt = parse_date(row.get("AwardDate", ""))
        if not award_dt or award_dt.year < 1990 or award_dt.year > 2100:
            award_dt = parse_date(row.get("PostedDate", ""))
        if not award_dt:
            continue
        month_key = f"{award_dt.year:04d}-{award_dt.month:02d}"
        month_display = f"{award_dt.month:02d}-01-{award_dt.year:04d}"
        bucket = by_month.setdefault(
            month_key,
            {"month_display": month_display, "month_key": month_key, "awarded": 0, "companies": set()},
        )
        bucket["awarded"] += 1
        bucket["companies"].add(awardee)

    sorted_months = sorted(by_month.values(), key=lambda item: item["month_key"], reverse=True)
    monthly = [
        {
            "month": item["month_display"],
            "awarded": item["awarded"],
            "unique_companies": len(item["companies"]),
        }
        for item in sorted_months
    ]

    leaders = [
        {"company": company, "awarded": count}
        for company, count in awardee_counts.most_common(25)
    ]

    return {
        "total_companies": len(awardee_counts),
        "top_companies": leaders,
        "monthly": monthly[:18],
    }


def extract_top_award_records(
    all_rows: list[dict[str, Any]],
    top_companies: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract individual award records for the top companies from all_rows.

    These records are saved to docs/data/award_records.json so the dashboard
    can filter by awarded company name.
    """
    top_set = {entry["company"] for entry in top_companies}
    records = []
    for row in all_rows:
        if not is_win(row):
            continue
        awardee = (row.get("Awardee") or "").strip()
        if not awardee or awardee.lower() == "null":
            continue
        if awardee not in top_set:
            continue
        records.append(
            {
                "NoticeId": row.get("NoticeId") or "",
                "Sol#": row.get("Sol#") or "",
                "Title": row.get("Title") or "",
                "Department/Ind.Agency": row.get("Department/Ind.Agency") or "",
                "Type": row.get("Type") or "",
                "PostedDate": row.get("PostedDate") or "",
                "Awardee": awardee,
                "Award$": row.get("Award$") or "",
                "Link": row.get("Link") or "",
                "matches": [],
            }
        )
    return records


def write_markdown_opportunities(records: list[dict[str, Any]], output_dir: Path) -> int:
    opportunities_dir = output_dir / "opportunities"
    opportunities_dir.mkdir(parents=True, exist_ok=True)
    written = 0

    for row in records:
        notice_id = (row.get("NoticeId") or "").strip()
        if not notice_id:
            continue

        doc_dir = opportunities_dir / notice_id
        doc_dir.mkdir(parents=True, exist_ok=True)

        title = (row.get("Title") or "Untitled Opportunity").strip()
        agency = (row.get("Department/Ind.Agency") or "Unknown Agency").strip()
        notice_type = (row.get("Type") or "Unknown Type").strip()
        posted = (row.get("PostedDate") or "").strip()
        sol_number = (row.get("Sol#") or "").strip()
        description = (row.get("Description") or "").strip()
        description = clean_description(description)
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
            markdown_lines.append(f"- [SAM.gov opportunity page]({sam_link})")
        if pdf_link:
            if pdf_link.lower().endswith(".pdf"):
                markdown_lines.append(f"- [PDF Attachment]({pdf_link})")
            else:
                markdown_lines.append(f"- [Additional Information]({pdf_link})")
        if not sam_link and not pdf_link:
            markdown_lines.append("_No links are available for this opportunity._")

        (doc_dir / "index.md").write_text("\n".join(markdown_lines), encoding="utf-8")
        row["has_markdown"] = True
        written += 1

    return written


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Process SAM.gov opportunities/wins for a target date"
    )
    parser.add_argument("--target-date", default=date.today().isoformat())
    parser.add_argument("--source-url", default=DEFAULT_CSV_URL)
    parser.add_argument("--terms", default="config/terms.yml")
    parser.add_argument("--output-dir", default="data/today")
    parser.add_argument("--docs-data-dir", default="docs/data")
    parser.add_argument(
        "--fallback-latest",
        action="store_true",
        help="Use latest available posted date if target date has no records",
    )
    parser.add_argument("--with-ollama", action="store_true")
    parser.add_argument("--ollama-model", default="gpt-oss:20b")
    parser.add_argument(
        "--llm-provider",
        choices=["ollama", "github"],
        default="ollama",
        help="Primary LLM provider (default: ollama)",
    )
    parser.add_argument(
        "--llm-fallback",
        action="store_true",
        help="Fallback to the alternate provider if the primary fails",
    )
    parser.add_argument("--github-model", default="gpt-4o-mini")
    parser.add_argument("--github-base-url", default="https://models.inference.ai.azure.com")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_data_dir = Path(args.docs_data_dir)
    docs_data_dir.mkdir(parents=True, exist_ok=True)

    terms = load_terms(Path(args.terms))

    if args.source_url.startswith(("http://", "https://")):
        response = requests.get(args.source_url, stream=True, timeout=90)
        response.raise_for_status()
        lines = (_decode_csv_line(line) for line in response.iter_lines() if line)
        reader = csv.DictReader(lines)
        all_rows = [row for row in reader]
    else:
        with open(args.source_url, "r", encoding="windows-1252", errors="replace") as f:
            reader = csv.DictReader(f)
            all_rows = [row for row in reader]

    target_records: list[dict[str, str]] = []
    latest_date = ""
    latest_records: list[dict[str, str]] = []

    for row in all_rows:
        posted = normalize_date(row.get("PostedDate", ""))
        if not posted:
            continue

        if posted == args.target_date:
            target_records.append(row)

        if posted > latest_date:
            latest_date = posted
            latest_records = [row]
        elif posted == latest_date:
            latest_records.append(row)

    effective_date = args.target_date
    records = target_records
    used_fallback = False

    if not records and args.fallback_latest:
        records = latest_records
        effective_date = latest_date
        used_fallback = True

    # Add attachment information to each record
    for row in records:
        description = row.get("Description", "")
        attachment_info = extract_attachments(description)
        row["AttachmentCount"] = attachment_info["count"]
        row["Attachments"] = attachment_info["attachments"]

    wins = [row for row in records if is_win(row)]
    opportunities = [row for row in records if not is_win(row)]
    type_counts = Counter((row.get("Type") or "Unknown Type").strip() for row in records)
    department_breakdown = build_department_breakdown(records)
    date_breakdown = build_date_breakdown(records)
    award_company_history = build_award_company_history(all_rows)
    award_records = extract_top_award_records(all_rows, award_company_history.get("top_companies", []))

    per_record_matches: list[dict[str, Any]] = []
    total_term_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()

    for row in records:
        text = f"{row.get('Title', '')}\n{row.get('Description', '')}"
        term_counts, details = scan_terms(text, terms)
        total_term_counts.update(term_counts)
        category_counts.update(details["categories"])
        
        # Add matches to the record for frontend filtering
        row["matches"] = details["terms"]
        
        if details["terms"]:
            per_record_matches.append(
                {
                    "NoticeId": row.get("NoticeId"),
                    "Sol#": row.get("Sol#"),
                    "Title": row.get("Title"),
                    "Type": row.get("Type"),
                    "PostedDate": row.get("PostedDate"),
                    "Agency": row.get("Department/Ind.Agency"),
                    "Link": row.get("Link"),
                    "matches": details["terms"][:8],
                }
            )

    per_record_matches.sort(
        key=lambda row: (
            normalize_date(row.get("PostedDate", "")),
            sum(match["count"] for match in row["matches"]),
        ),
        reverse=True,
    )

    ollama_results: list[dict[str, Any]] = []
    if records:
        if args.with_ollama:
            args.llm_provider = "ollama"

        primary_client = None
        fallback_client = None

        if args.llm_provider == "ollama":
            primary_client = OllamaClient(model=args.ollama_model)
            if not (primary_client.health_check() and args.ollama_model in primary_client.list_models()):
                primary_client = None
            fallback_client = GitHubModelsClient(base_url=args.github_base_url, model=args.github_model)
            if not fallback_client.is_configured():
                fallback_client = None
        else:
            primary_client = GitHubModelsClient(base_url=args.github_base_url, model=args.github_model)
            if not primary_client.is_configured():
                primary_client = None
            fallback_client = OllamaClient(model=args.ollama_model)
            if not (fallback_client.health_check() and args.ollama_model in fallback_client.list_models()):
                fallback_client = None

        if not primary_client and args.llm_fallback:
            primary_client, fallback_client = fallback_client, None

        if primary_client:
            for row in records:
                compact_record = {
                    "AGENCY": row.get("Department/Ind.Agency"),
                    "SUBJECT": row.get("Title"),
                    "DESC": row.get("Description"),
                    "SOLNBR": row.get("Sol#") or row.get("NoticeId"),
                    "URL": row.get("Link"),
                }
                result = analyze_record(primary_client, compact_record, task="assess_relevance")
                if (not result or not result.strip()) and args.llm_fallback and fallback_client:
                    result = analyze_record(fallback_client, compact_record, task="assess_relevance")
                    used_provider = getattr(fallback_client, "provider", "unknown")
                    used_model = getattr(fallback_client, "model", "unknown")
                else:
                    used_provider = getattr(primary_client, "provider", "unknown")
                    used_model = getattr(primary_client, "model", "unknown")

                if result:
                    ollama_results.append(
                        {
                            "NoticeId": row.get("NoticeId"),
                            "Title": row.get("Title"),
                            "Type": row.get("Type"),
                            "relevance": result.strip(),
                            "provider": used_provider,
                            "model": used_model,
                        }
                    )

    summary = {
        "requested_date": args.target_date,
        "effective_date": effective_date,
        "used_fallback_latest": used_fallback,
        "latest_available_date": latest_date,
        "records_total": len(records),
        "opportunities_total": len(opportunities),
        "wins_total": len(wins),
        "awarded_total": len(wins),
        "departments_total": len(department_breakdown),
        "top_terms": total_term_counts.most_common(20),
        "category_counts": category_counts.most_common(),
        "type_breakdown": type_counts.most_common(),
        "department_breakdown": department_breakdown,
        "date_breakdown": date_breakdown,
        "award_company_history": award_company_history,
        "top_matching_records": per_record_matches[:30],
    }

    relationships = to_relationships(records)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (output_dir / "records.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )
    (output_dir / "opportunities.json").write_text(
        json.dumps(opportunities, indent=2), encoding="utf-8"
    )
    (output_dir / "wins.json").write_text(json.dumps(wins, indent=2), encoding="utf-8")
    (output_dir / "relationships.json").write_text(
        json.dumps(relationships, indent=2), encoding="utf-8"
    )
    (output_dir / "ollama_relevance.json").write_text(
        json.dumps(ollama_results, indent=2), encoding="utf-8"
    )

    dept_lines = [
        "# Department-by-Department Breakdown",
        "",
        f"Effective date: {effective_date}",
        f"Requested date: {args.target_date}",
        f"Total records: {len(records)}",
        f"Departments: {len(department_breakdown)}",
        "",
        "| Department | Total | Opportunities | Wins |",
        "|---|---:|---:|---:|",
    ]
    for row in department_breakdown:
        dept_lines.append(
            f"| {row['department']} | {row['total']} | {row['opportunities']} | {row['wins']} |"
        )
    (output_dir / "department_breakdown.md").write_text(
        "\n".join(dept_lines), encoding="utf-8"
    )

    (docs_data_dir / "today_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    (docs_data_dir / "today_relationships.json").write_text(
        json.dumps(relationships, indent=2), encoding="utf-8"
    )
    (docs_data_dir / "today_departments.json").write_text(
        json.dumps(department_breakdown, indent=2), encoding="utf-8"
    )
    (docs_data_dir / "award_records.json").write_text(
        json.dumps(award_records, indent=2), encoding="utf-8"
    )

    markdown_written = write_markdown_opportunities(records, docs_data_dir.parent)

    (docs_data_dir / "today_records.json").write_text(
        json.dumps(records, indent=2), encoding="utf-8"
    )

    print(f"Requested date: {args.target_date}")
    print(f"Effective date: {effective_date}")
    print(f"Fallback used: {used_fallback}")
    print(f"Total records: {len(records)}")
    print(f"Opportunities: {len(opportunities)}")
    print(f"Wins: {len(wins)}")
    print(f"Markdown docs written: {markdown_written}")
    print(f"Wrote outputs to {output_dir}")
    print(f"Wrote docs data to {docs_data_dir}")


if __name__ == "__main__":
    main()