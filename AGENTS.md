# AGENTS.md

## Project overview
- Purpose: ingest SAM.gov contract opportunities, extract/search digital-service signals, and publish a GitHub Pages dashboard.
- Primary runtime: Python scripts in the scripts directory.
- Primary generated artifacts:
  - data/today (daily processed outputs)
  - data/opportunities.sqlite (dedup + persistence)
  - docs/data (dashboard JSON payloads)

## Setup commands
- Create environment:
  - python3 -m venv .venv
  - source .venv/bin/activate
- Install dependencies:
  - pip install requests beautifulsoup4 lxml playwright pyyaml
  - python -m playwright install chromium

## Core workflows
- Daily processing:
  - python scripts/process_today.py --target-date YYYY-MM-DD --fallback-latest
- Dedup and persistence:
  - python scripts/persist_to_sqlite.py
- High-value alert generation:
  - python scripts/generate_alerts.py --min-hits 8
- USASpending market intelligence enrichment:
  - python scripts/enrich_usaspending.py
- Historical scan and report rebuild:
  - python scripts/scan_terms.py --md-dir data/samples_md --terms config/terms.yml --output data/term_scan_report.json
  - python scripts/analyze_matches.py

## Automation
- Daily workflow: .github/workflows/ingest.yml
  - Processes daily feed
  - Persists to SQLite
  - Generates high-value alerts
  - Enriches alerts with USASpending market intelligence (vendor landscape, contract counts)
  - Exports department trends and contract officer intelligence
  - Runs departmental forecasting
  - Creates GitHub issue for high-value matches (if any)
- Weekly workflow: .github/workflows/weekly-pdf-extraction.yml
  - Downloads latest CSV
  - Refreshes opportunities, persistence, alerts, and trends
  - Exports all opportunities for search
  - Extracts PDFs from top opportunities

## Coding conventions
- Keep scripts idempotent and file-path configurable via CLI flags.
- Prefer deterministic JSON outputs with stable keys and sorted summaries where practical.
- Avoid introducing external services for core ingestion; default to public SAM.gov extracts and local processing.
- Keep changes minimal and focused; preserve existing file formats expected by downstream scripts.
- Follow the Python coding standards documented in **PYTHON_GUIDANCE.md** when writing or reviewing Python scripts.

## Testing and validation
- Run targeted checks after edits:
  - python scripts/process_today.py --target-date YYYY-MM-DD --fallback-latest
  - python scripts/persist_to_sqlite.py
  - python scripts/generate_alerts.py
- For dashboard changes, serve docs locally:
  - python -m http.server 8000 --directory docs

## Data and safety considerations
- Do not commit secrets or tokens.
- Use only public SAM.gov data feeds in automation.
- Treat generated artifacts as reproducible outputs; avoid manual edits under data/today and docs/data.

## Collaboration notes for agents
- Prefer root-cause fixes over one-off patches.
- If requirements are ambiguous, choose the simplest implementation that fits current scripts and outputs.
- When adding new outputs, update both README.md and any dependent workflow steps.
- When modifying the GitHub Pages dashboard (docs/), follow the accessibility guidelines in ACCESSIBILITY.md.
- When using AI tools to build or modify this project, update the **AI Disclosure** section in README.md to reflect which AI tools were used and how (development assistance, runtime use, CI/CD automation, or browser-based). Do not list tools that were not actually used.
