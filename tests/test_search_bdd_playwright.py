"""Playwright pilot tests mapped to search.feature scenarios."""

from __future__ import annotations

import contextlib
import os
import socket
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest

playwright_sync_api = pytest.importorskip("playwright.sync_api")


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


pytestmark = pytest.mark.ui


def _port_is_open(port: int) -> bool:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_http(url: str, timeout_seconds: float = 15) -> None:
    end = time.time() + timeout_seconds
    while time.time() < end:
        try:
            with urlopen(url):
                return
        except URLError:
            time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for {url}")


@pytest.fixture(scope="module")
def docs_server() -> Generator[str, None, None]:
    if os.getenv("RUN_PLAYWRIGHT_BDD") != "1":
        pytest.skip("Set RUN_PLAYWRIGHT_BDD=1 to run Playwright BDD pilot tests")

    port = 8000
    if _port_is_open(port):
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_http(f"{base_url}/search.html")
        yield base_url
        return

    proc = subprocess.Popen(
        ["python", "-m", "http.server", str(port), "--directory", str(DOCS_DIR)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_http(f"{base_url}/search.html")
        yield base_url
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.mark.fast
def test_scenario_search_keyword_returns_results(docs_server: str) -> None:
    """Scenario: Search by keyword returns visible opportunities."""
    with playwright_sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{docs_server}/search.html")
            page.fill("#search-input", "web")
            page.wait_for_selector("#search-stats")
            stats = page.text_content("#search-stats") or ""
            assert "Found" in stats
            assert page.locator(".result-item").count() > 0
        finally:
            browser.close()


@pytest.mark.slow
def test_scenario_status_open_shows_only_open_results(docs_server: str) -> None:
    """Scenario: Filtering by open status narrows results to open opportunities."""
    with playwright_sync_api.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(f"{docs_server}/search.html")
            page.select_option("#filter-status", "open")
            page.wait_for_selector("#active-filters .filter-chip")
            filter_chips = page.locator("#active-filters .filter-chip").all_text_contents()
            assert any("Open Opportunities" in chip for chip in filter_chips)

            statuses = page.locator(".result-title .badge-opportunity").all_text_contents()
            assert statuses, "Expected at least one open result"
            assert all("Open" in text for text in statuses)
        finally:
            browser.close()
