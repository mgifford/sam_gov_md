# Definition of Done

This document defines the acceptance criteria for the SAM.gov Contract Opportunities Explorer.
Each section describes a deliverable, what "done" means for it, and how a CivicActions team
member can verify it independently.

For a full list of implemented features, see [FEATURES.md](FEATURES.md).
For setup instructions, see [README.md](README.md) and [AGENTS.md](AGENTS.md).

---

## How to use this document

Each deliverable below contains:

- **What it does** — brief description.
- **Done when** — specific, testable conditions.
- **How to test** — exact commands or steps a reviewer can run locally or in the browser.

All tests assume the virtual environment is active:

```bash
source .venv/bin/activate
```

---

## 1. Daily opportunity ingestion

**What it does:** Downloads the SAM.gov full CSV feed, filters to today's records, scores them against ICT/digital terms, and writes structured JSON outputs.

**Done when:**
- Running `process_today.py` on any valid date produces non-empty `data/today/summary.json`.
- `data/today/opportunities.json` contains records with `matches` and `score` fields.
- `data/today/high_value_matches.json` contains only records that have at least one focus-term match or a digital NAICS/PSC code.
- `docs/data/today_summary.json`, `today_relationships.json`, and `today_departments.json` are updated.

**How to test:**

```bash
python scripts/process_today.py --target-date 2026-03-04 --fallback-latest
# Expect: "Wrote data/today/summary.json" and similar messages
cat data/today/summary.json | python -m json.tool | head -20
# Expect: JSON with total_opportunities, total_wins, top_agencies
cat data/today/opportunities.json | python -c "import sys,json; d=json.load(sys.stdin); print(len(d),'records')"
# Expect: positive integer
```

---

## 2. SQLite deduplication and persistence

**What it does:** Upserts daily records into a SQLite database, tracking when each notice was first seen, last seen, and how many times.

**Done when:**
- Running `persist_to_sqlite.py` creates or updates `data/opportunities.sqlite`.
- Re-running on the same data does not duplicate records (idempotent).
- Each record has `first_seen_date`, `last_seen_date`, and `seen_count` fields.

**How to test:**

```bash
python scripts/persist_to_sqlite.py
# Expect: "Upserted N records" message

python -c "
import sqlite3
conn = sqlite3.connect('data/opportunities.sqlite')
count = conn.execute('SELECT COUNT(*) FROM opportunities').fetchone()[0]
print('Total records in DB:', count)
dupes = conn.execute('SELECT notice_id, COUNT(*) FROM opportunities GROUP BY notice_id HAVING COUNT(*) > 1').fetchall()
print('Duplicate notice IDs:', len(dupes))
"
# Expect: positive total, 0 duplicates
```

---

## 3. High-value alert generation

**What it does:** Selects the most relevant opportunities from today's data and writes alert files for human review and GitHub Issues.

**Done when:**
- `data/today/high_value_matches.json` contains records that each have at least one focus-term match or digital NAICS/PSC.
- `data/today/high_value_alert.md` is a readable Markdown report listing each match with title, agency, URL, and matched terms.
- `data/today/alerts_summary.json` contains metadata (count, threshold used, date).

**How to test:**

```bash
python scripts/generate_alerts.py --min-hits 8
# Expect: "Wrote data/today/high_value_matches.json" message

# Verify matches have focus-term hits or NAICS signals
python -c "
import json
matches = json.load(open('data/today/high_value_matches.json'))
print('High-value matches:', len(matches))
for m in matches[:3]:
    print(' -', m.get('Title','')[:60], '| score:', m.get('score',0))
"

# Read the alert report
head -60 data/today/high_value_alert.md
# Expect: Markdown with opportunity titles, agencies, and term-match lists
```

---

## 4. Departmental opportunity investigation

This is the primary research workflow for CivicActions team members exploring which agencies have the most relevant pipeline.

### 4a. Dashboard department panel

**Done when:**
- The main dashboard shows a "Department Breakdown" panel with opportunity and award counts per agency.
- Each entry links to that agency's filtered view.

**How to test:**

```bash
python scripts/process_today.py --target-date 2026-03-04 --fallback-latest
python -m http.server 8000 --directory docs &
open http://localhost:8000
# Navigate to the "Department Breakdown" panel
# Expect: list of agencies with counts; clicking an agency filters the list
```

### 4b. Department trends over time

**Done when:**
- `docs/data/trends.json` contains daily counts per agency across multiple dates.
- `docs/trends.html` renders agency sparklines and a top-agencies bar chart.
- Trends data updates each time `export_trends.py` runs.

**How to test:**

```bash
python scripts/export_trends.py
# Expect: "Wrote docs/data/trends.json"

python -c "
import json
trends = json.load(open('docs/data/trends.json'))
print('Agencies in trends:', len(trends.get('agencies',{})))
"
# Expect: positive count

open http://localhost:8000/trends.html
# Expect: department sparklines, historical bar chart, agency filter
```

### 4c. Departmental forecasting

**Done when:**
- `docs/data/department_forecast.json` contains per-department aggregates: opportunity count, award count, total award value.
- The file updates automatically during the daily ingest workflow.

**How to test:**

```bash
python scripts/department_forecasting.py
# Expect: "Wrote docs/data/department_forecast.json"

python -c "
import json
forecast = json.load(open('docs/data/department_forecast.json'))
depts = forecast.get('departments', {})
print('Departments forecast:', len(depts))
for name, data in list(depts.items())[:5]:
    print(f'  {name}: {data.get(\"opportunity_count\",0)} opps, {data.get(\"award_count\",0)} awards')
"
```

### 4d. Contract officer intelligence

**Done when:**
- `docs/data/contract_officers.json` contains officer profiles with: name, email, departments served, opportunity count, award count, and total award value.

**How to test:**

```bash
python scripts/extract_contract_officers.py
# Expect: "Wrote docs/data/contract_officers.json"

python -c "
import json
officers = json.load(open('docs/data/contract_officers.json'))
print('Officers extracted:', len(officers.get('officers', [])))
"
```

### 4e. USASpending market intelligence enrichment

**Done when:**
- `data/today/usaspending_enrichment.json` contains vendor landscape data for each (NAICS, agency) pair from high-value matches.
- `data/today/high_value_alert.md` includes a **Market Intelligence** section for each match showing 3-year contract counts and top vendors.

**How to test:**

```bash
python scripts/enrich_usaspending.py
# Expect: "Enriched N matches" message

python -c "
import json
enrichment = json.load(open('data/today/usaspending_enrichment.json'))
print('Enriched matches:', len(enrichment))
"

grep 'Market Intelligence' data/today/high_value_alert.md
# Expect: at least one match
```

---

## 5. GitHub Pages dashboard

**Done when:**
- All four pages (`index.html`, `trends.html`, `time_to_award.html`, `search.html`) load without JavaScript errors.
- The main dashboard displays today's summary cards, department breakdown, top matches, and relationship graph.
- The search page returns results for common ICT terms (e.g., "accessibility", "web", "508").
- All pages are keyboard-navigable and pass basic accessibility checks.

**How to test:**

```bash
python -m http.server 8000 --directory docs

# Open each page and check:
# http://localhost:8000           — main dashboard
# http://localhost:8000/trends.html     — department trends
# http://localhost:8000/time_to_award.html  — award analytics
# http://localhost:8000/search.html     — full-text search

# Search test:
# 1. Open http://localhost:8000/search.html
# 2. Type "accessibility" in the search box
# 3. Expect: list of matching opportunities

# Accessibility check (requires axe-cli):
npx axe http://localhost:8000 --exit
npx axe http://localhost:8000/search.html --exit
# Expect: 0 critical violations
```

---

## 6. Automated daily ingest (GitHub Actions)

**Done when:**
- The `ingest.yml` workflow runs successfully on schedule and on manual trigger.
- The workflow creates a GitHub Issue when high-value matches are found.
- Artifact files in `data/today/` and `docs/data/` are committed and pushed after each run.

**How to test:**

1. In GitHub → Actions → **Daily SAM.gov ingest** → **Run workflow** → click **Run workflow**.
2. Monitor the run until it completes (green checkmark).
3. Verify a new commit appears on `main` with updated `data/today/` and `docs/data/` files.
4. If high-value matches were found, verify a GitHub Issue was opened with alert content.

---

## 7. Search index

**Done when:**
- `docs/data/opportunities_search.json` (or equivalent search index file) contains all exported opportunities with searchable fields.
- The search page returns relevant results for ICT keywords within 1 second of typing.
- Results can be filtered by agency, notice type, and date range.

**How to test:**

```bash
python scripts/export_all_opportunities.py
# Expect: search index written to docs/data/

# Open search page and test:
# http://localhost:8000/search.html
# Filter: agency = "DEPT OF DEFENSE" → expect DoD opportunities only
# Filter: notice type = "Award Notice" → expect only award records
# Filter: date range → expect records within range only
```

---

## 8. Accessibility conformance (WCAG 2.2 AA)

**Done when:**
- All `docs/` pages pass the automated axe-core regression tests in `tests/test_docs_accessibility.py`.
- No heading levels are skipped on any page.
- All interactive elements have visible focus indicators.
- All SVG charts have `<title>` and `aria-labelledby`.
- The `a11y-scan.yml` workflow runs without critical violations.

**How to test:**

```bash
python -m pytest tests/test_docs_accessibility.py -v
# Expect: all tests pass

# Optional (requires axe-cli):
npx axe http://localhost:8000 --exit
```

---

## 9. Automated test suite

**Done when:**
- All tests in `tests/` pass without modification.
- No tests are removed or skipped to make the suite pass.

**How to test:**

```bash
python -m pytest tests/ \
  --ignore=tests/test_scrape_opportunities.py \
  --ignore=tests/test_explore_extracts.py \
  -v
# Expect: all collected tests pass
```

*(The two ignored files require optional dependencies — `docx` and Playwright — that are not installed in CI.)*

---

## 10. Documentation completeness

**Done when:**
- `README.md` accurately reflects the current capabilities and setup steps.
- `FEATURES.md` lists all implemented scripts and dashboard pages.
- `AGENTS.md` contains accurate setup, workflow, and validation commands.
- `ACCESSIBILITY.md` documents the accessibility standard and how to verify it.
- The AI Disclosure section in `README.md` is up to date with all AI tools actually used.

**How to test:**

- Open each file and verify that every script listed in `scripts/` is mentioned in either `README.md` or `FEATURES.md`.
- Verify that the setup commands in `AGENTS.md` and `README.md` produce a working environment from scratch.

---

## Quick verification checklist

Use this as a 15-minute smoke test after any significant change:

```bash
# 1. Activate environment
source .venv/bin/activate

# 2. Run daily pipeline
python scripts/process_today.py --fallback-latest
python scripts/persist_to_sqlite.py
python scripts/generate_alerts.py --min-hits 8

# 3. Run departmental tools
python scripts/export_trends.py
python scripts/department_forecasting.py
python scripts/extract_contract_officers.py

# 4. Run tests
python -m pytest tests/ \
  --ignore=tests/test_scrape_opportunities.py \
  --ignore=tests/test_explore_extracts.py \
  -q
# Expect: all pass

# 5. Serve dashboard
python -m http.server 8000 --directory docs
# Open http://localhost:8000 and visually verify the dashboard loads
```
