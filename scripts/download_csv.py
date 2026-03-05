#!/usr/bin/env python3
"""Download the SAM.gov Contract Opportunities full CSV extract."""

from __future__ import annotations

import argparse
import os
import time
from typing import Optional

import requests

DEFAULT_CSV_URL = (
    "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/"
    "ContractOpportunitiesFullCSV.csv"
)
DEFAULT_OUTPUT = "data/ContractOpportunitiesFullCSV.csv"


def download_csv(
    url: str,
    dest_path: str,
    retries: int = 3,
    backoff: float = 2.0,
    timeout: int = 300,
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
    last_err: Optional[Exception] = None
    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading {url} -> {dest_path} (attempt {attempt})")
            with requests.get(url, stream=True, timeout=timeout) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("Content-Length")
                if content_length:
                    print(f"  File size: {int(content_length) / 1024 / 1024:.1f} MB")
                downloaded = 0
                with open(dest_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
            size_mb = os.path.getsize(dest_path) / 1024 / 1024
            print(f"  Downloaded {size_mb:.1f} MB to {dest_path}")
            return
        except Exception as exc:
            last_err = exc
            print(f"  Attempt {attempt} failed: {exc}")
            if attempt < retries:
                sleep_for = backoff ** attempt
                print(f"  Retrying in {sleep_for:.0f}s...")
                time.sleep(sleep_for)
    raise RuntimeError(f"Failed to download {url} after {retries} attempts: {last_err}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download the SAM.gov ContractOpportunitiesFullCSV.csv extract"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_CSV_URL,
        help="URL of the CSV extract (default: SAM.gov S3 bucket)",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Destination file path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Number of download retries (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Request timeout in seconds (default: 300)",
    )
    args = parser.parse_args()

    download_csv(
        url=args.url,
        dest_path=args.output,
        retries=args.retries,
        timeout=args.timeout,
    )


if __name__ == "__main__":
    main()
