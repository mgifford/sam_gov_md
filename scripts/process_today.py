#!/usr/bin/env python3
"""Process SAM.gov Contract Opportunities for a target date and generate web-ready outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import requests
import yaml

from ollama_analyzer import OllamaClient, analyze_record

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


def is_win(row: dict[str, str]) -> bool:
    notice_type = (row.get("Type") or "").lower()
    return "award" in notice_type or "win" in notice_type


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
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    docs_data_dir = Path(args.docs_data_dir)
    docs_data_dir.mkdir(parents=True, exist_ok=True)

    terms = load_terms(Path(args.terms))

    response = requests.get(args.source_url, stream=True, timeout=90)
    response.raise_for_status()
    lines = (line.decode("utf-8", "replace") for line in response.iter_lines() if line)
    reader = csv.DictReader(lines)

    target_records: list[dict[str, str]] = []
    latest_date = ""
    latest_records: list[dict[str, str]] = []

    for row in reader:
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

    wins = [row for row in records if is_win(row)]
    opportunities = [row for row in records if not is_win(row)]
    type_counts = Counter((row.get("Type") or "Unknown Type").strip() for row in records)
    department_breakdown = build_department_breakdown(records)

    per_record_matches: list[dict[str, Any]] = []
    total_term_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()

    for row in records:
        text = f"{row.get('Title', '')}\n{row.get('Description', '')}"
        term_counts, details = scan_terms(text, terms)
        total_term_counts.update(term_counts)
        category_counts.update(details["categories"])
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
        key=lambda row: sum(match["count"] for match in row["matches"]), reverse=True
    )

    ollama_results: list[dict[str, Any]] = []
    if args.with_ollama and records:
        client = OllamaClient(model=args.ollama_model)
        if client.health_check() and args.ollama_model in client.list_models():
            for row in records:
                compact_record = {
                    "AGENCY": row.get("Department/Ind.Agency"),
                    "SUBJECT": row.get("Title"),
                    "DESC": row.get("Description"),
                    "SOLNBR": row.get("Sol#") or row.get("NoticeId"),
                    "URL": row.get("Link"),
                }
                result = analyze_record(client, compact_record, task="assess_relevance")
                if result:
                    ollama_results.append(
                        {
                            "NoticeId": row.get("NoticeId"),
                            "Title": row.get("Title"),
                            "Type": row.get("Type"),
                            "relevance": result.strip(),
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
        "departments_total": len(department_breakdown),
        "top_terms": total_term_counts.most_common(20),
        "category_counts": category_counts.most_common(),
        "type_breakdown": type_counts.most_common(),
        "department_breakdown": department_breakdown,
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

    print(f"Requested date: {args.target_date}")
    print(f"Effective date: {effective_date}")
    print(f"Fallback used: {used_fallback}")
    print(f"Total records: {len(records)}")
    print(f"Opportunities: {len(opportunities)}")
    print(f"Wins: {len(wins)}")
    print(f"Wrote outputs to {output_dir}")
    print(f"Wrote docs data to {docs_data_dir}")


if __name__ == "__main__":
    main()