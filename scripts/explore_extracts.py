#!/usr/bin/env python3
"""Download a few recent SAM.gov daily extracts and inspect their contents."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup
from lxml import etree
from playwright.sync_api import sync_playwright

HISTORICAL_URL = (
    "https://sam.gov/data-services/Contract%20Opportunities/daily/historical"
    "?privacy=Public"
)
LISTFILES_URL = "https://sam.gov/api/prod/fileextractservices/v1/api/listfiles"


@dataclass
class ExtractLink:
    url: str
    date_key: str
    file_format: str = ""


def fetch_html(url: str, retries: int = 3, backoff: float = 1.5) -> str:
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:  # pragma: no cover - network errors
            last_err = exc
            sleep_for = backoff ** attempt
            time.sleep(sleep_for)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def fetch_html_with_playwright(url: str, timeout_ms: int = 45000) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            return page.content()
        finally:
            browser.close()


def normalize_url(base: str, href: str) -> Optional[str]:
    if not href:
        return None
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return "https://sam.gov" + href
    return None


def discover_extract_links(html: str) -> list[ExtractLink]:
    soup = BeautifulSoup(html, "lxml")
    links: list[ExtractLink] = []
    for a in soup.find_all("a"):
        href = a.get("href", "").strip()
        if not href.lower().endswith((".zip", ".json", ".xml")):
            continue
        url = normalize_url("https://sam.gov", href)
        if not url:
            continue
        # Try to infer date from filename, fall back to url order.
        m = re.search(r"(20\d{2}[-_]?\d{2}[-_]?\d{2})", url)
        date_key = m.group(1).replace("-", "").replace("_", "") if m else url
        links.append(ExtractLink(url=url, date_key=date_key))
    # Sort newest first by inferred date_key.
    links.sort(key=lambda item: item.date_key, reverse=True)
    return links


def discover_extract_links_api() -> list[ExtractLink]:
    params = {
        "domain": "Contract Opportunities/daily/historical",
        "privacy": "Public",
        "random": str(int(time.time())),
    }
    resp = requests.get(LISTFILES_URL, params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    items = payload.get("_embedded", {}).get("customS3ObjectSummaryList", [])
    links: list[ExtractLink] = []
    for item in items:
        href = item.get("_links", {}).get("self", {}).get("href")
        if not href:
            continue
        file_format = str(item.get("fileFormat") or "").lower()
        if file_format not in {"xml", "csv", "zip", "json"}:
            continue
        date_key = (
            str(item.get("displayKey") or item.get("dateModified") or href)
            .replace("-", "")
            .replace("_", "")
            .replace(",", "")
            .replace(" ", "")
        )
        links.append(ExtractLink(url=href, date_key=date_key, file_format=file_format))
    links.sort(key=lambda item: item.date_key, reverse=True)
    return links


def stream_download(url: str, dest_path: str, retries: int = 3, backoff: float = 1.5) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=60) as resp:
                resp.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            return
        except Exception as exc:  # pragma: no cover - network errors
            last_err = exc
            time.sleep(backoff ** attempt)
    raise RuntimeError(f"Failed to download {url}: {last_err}")


def iter_json_records(path: str) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("opportunities", "data", "results"):
            if isinstance(data.get(key), list):
                return data[key]
    raise ValueError(f"Unrecognized JSON structure in {path}")


def save_markdown(md_dir: Optional[str], name: str, content: str) -> None:
    if not md_dir:
        return
    os.makedirs(md_dir, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    out_path = os.path.join(md_dir, f"{safe_name}.md")
    with open(out_path, "w", encoding="utf-8", errors="replace") as out:
        out.write(f"# {name}\n\n")
        out.write(content)


def inspect_zip(
    zip_path: str,
    max_records: int,
    save_dir: Optional[str],
    md_dir: Optional[str],
    analysis: dict,
) -> None:
    print(f"\n=== {os.path.basename(zip_path)} ===")
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
            print("Files:")
            for name in names:
                print(f"- {name}")
            json_names = [n for n in names if n.lower().endswith(".json")]
            if not json_names:
                print("No JSON files found.")
                for name in names:
                    with zf.open(name) as inner:
                        raw = inner.read()
                    text = raw.decode("utf-8", errors="replace")
                    save_markdown(md_dir, f"{os.path.basename(zip_path)}::{name}", text)
                return
            first_json = json_names[0]
            print(f"\nInspecting {first_json} ...")
            with zf.open(first_json) as jf:
                data = json.load(jf)
            if isinstance(data, list):
                records = data
            elif isinstance(data, dict):
                records = None
                for key in ("opportunities", "data", "results"):
                    if isinstance(data.get(key), list):
                        records = data[key]
                        print(f"Top-level key: {key}")
                        break
                if records is None:
                    print("Unrecognized JSON structure.")
                    return
            else:
                print("JSON not list/dict; cannot inspect.")
                return
            print(f"Records: {len(records)}")
            analysis["record_counts"].append(len(records))
            for idx, rec in enumerate(records[:max_records], start=1):
                print(f"\nRecord {idx} keys:")
                print(", ".join(sorted(rec.keys())))
                print("Sample record:")
                print(json.dumps(rec, indent=2)[:4000])
            save_markdown(
                md_dir,
                os.path.basename(zip_path),
                json.dumps(records[:max_records], indent=2)[:20000],
            )
    except zipfile.BadZipFile:
        print("Not a zip file; inspecting as text/XML...")
        with open(zip_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read(50000)
        snippet = text[:2000]
        print("Preview:")
        print(snippet)
        save_markdown(md_dir, os.path.basename(zip_path), text)

        analysis["file_samples"].append(
            {"file": os.path.basename(zip_path), "preview": snippet}
        )

        if "<" in text and ">" in text:
            print("\nAttempting XML parse...")
            try:
                wrapped = f"<ROOT>{text}</ROOT>"
                root = etree.fromstring(wrapped.encode("utf-8", errors="ignore"))
                # Find the first child element that looks like a record.
                record = None
                for child in root:
                    if isinstance(child.tag, str):
                        record = child
                        break
                if record is None:
                    raise ValueError("No child elements found")
                record_dict = {}
                for elem in record:
                    if not isinstance(elem.tag, str):
                        continue
                    record_dict[elem.tag] = (elem.text or "").strip()
                print("Parsed XML record:")
                print(json.dumps(record_dict, indent=2)[:4000])
                analysis["tag_sets"].append(sorted(record_dict.keys()))
                if save_dir:
                    os.makedirs(save_dir, exist_ok=True)
                    out_path = os.path.join(
                        save_dir, f"{os.path.basename(zip_path)}.sample.json"
                    )
                    with open(out_path, "w", encoding="utf-8") as out:
                        json.dump(record_dict, out, indent=2, sort_keys=True)
                    print(f"Saved sample JSON to {out_path}")
            except Exception:
                print("XML parse failed; extracting tag/value pairs...")
                pairs = re.findall(r"<([A-Z0-9_]+)>([^<\n\r]*)", text, re.IGNORECASE)
                record_dict = {}
                for tag, value in pairs[:200]:
                    tag = tag.strip().upper()
                    if tag not in record_dict and value.strip():
                        record_dict[tag] = value.strip()
                if record_dict:
                    print("Tag/value sample:")
                    print(json.dumps(record_dict, indent=2)[:4000])
                    analysis["tag_sets"].append(sorted(record_dict.keys()))
                    if save_dir:
                        os.makedirs(save_dir, exist_ok=True)
                        out_path = os.path.join(
                            save_dir, f"{os.path.basename(zip_path)}.sample.json"
                        )
                        with open(out_path, "w", encoding="utf-8") as out:
                            json.dump(record_dict, out, indent=2, sort_keys=True)
                        print(f"Saved sample JSON to {out_path}")
                else:
                    print("No tag/value pairs found.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=2, help="How many newest zips to download")
    parser.add_argument(
        "--out",
        default="data/samples",
        help="Download directory for sample zips",
    )
    parser.add_argument(
        "--records",
        type=int,
        default=1,
        help="How many records to display per JSON",
    )
    parser.add_argument(
        "--save-sample",
        default=None,
        help="Directory to save extracted sample records as JSON",
    )
    parser.add_argument(
        "--save-md",
        default=None,
        help="Directory to save markdown extractions",
    )
    parser.add_argument(
        "--report",
        default="data/samples_report.json",
        help="Path to write a JSON analysis report",
    )
    args = parser.parse_args()

    html = fetch_html(HISTORICAL_URL)
    links = discover_extract_links(html)
    if not links:
        print("No file links found in static HTML; retrying with Playwright...")
        html = fetch_html_with_playwright(HISTORICAL_URL)
        links = discover_extract_links(html)
    if not links:
        print("No file links found in rendered HTML; using listfiles API...")
        links = discover_extract_links_api()
    if not links:
        raise RuntimeError("No .zip links found")

    selected = links[: args.limit]
    print(f"Found {len(links)} extract links; downloading {len(selected)}")

    analysis = {"record_counts": [], "tag_sets": [], "file_samples": []}

    for link in selected:
        filename = os.path.basename(link.url.split("?")[0])
        dest_path = os.path.join(args.out, filename)
        if not os.path.exists(dest_path):
            print(f"Downloading {link.url} -> {dest_path}")
            stream_download(link.url, dest_path)
        else:
            print(f"Using cached {dest_path}")
        inspect_zip(dest_path, args.records, args.save_sample, args.save_md, analysis)

    with open(args.report, "w", encoding="utf-8") as out:
        json.dump(analysis, out, indent=2)
    print(f"Wrote report to {args.report}")


if __name__ == "__main__":
    main()
