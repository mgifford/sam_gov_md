# SAM.gov Contract Opportunities Explorer & Pipeline

Toolkit for discovering, analyzing, and tracking ICT/digital project opportunities from SAM.gov (formerly FBOps) contract data feeds.

## What This Does

- **Discovers** SAM.gov daily/historical extract files via web scraping + API
- **Downloads** and inspects XML/JSON/ZIP extracts
- **Parses** legacy FBO XML records into structured JSON
- **Extracts** text as Markdown for full-text search
- **Scans** for ICT/digital terms (accessibility, web, software, eLearning, etc.)
- **Reports** top matching opportunities with URLs and snippets

## Current Status

✅ **Completed**
- Discovery script with Playwright + SAM.gov API fallback
- XML-to-JSON sample extraction
- Markdown export for all records
- Regex-based term scanning with 50+ ICT keywords
- Top matches report with URLs and context

🚧 **In Progress**
- Full pipeline integration with Ollama + spec-kitty
- GitHub Actions automation
- PDF attachment download & conversion
- SQLite deduplication
- GitHub Pages search index

## Quick Start

### Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # or `.venv/bin/activate` on macOS/Linux

# Install dependencies
pip install requests beautifulsoup4 lxml playwright pyyaml

# Install Playwright browser
python -m playwright install chromium
```

### Explore Extracts

Download and inspect recent SAM.gov extract files:

```bash
python scripts/explore_extracts.py \
  --limit 25 \
  --records 1 \
  --save-sample data/samples_json \
  --save-md data/samples_md \
  --report data/samples_report.json
```

**Options**:
- `--limit N`: Download N most recent files (default: 2)
- `--records N`: Show N records per file (default: 1)
- `--save-sample DIR`: Save extracted JSON records
- `--save-md DIR`: Save markdown extractions
- `--report PATH`: Write analysis summary JSON

### Analyze Matches

Generate a report of top ICT/digital project matches:

```bash
python scripts/analyze_matches.py
```

Output: `data/top_matches_report.md`

### Scan for Terms

The term scanner uses regex patterns defined in `config/terms.yml` to find:
- **Technology**: software, web, API, cloud, CMS, Drupal, SharePoint
- **Accessibility**: Section 508, WCAG, VPAT, OpenACR
- **eLearning**: LMS, courseware, instructional design
- **UX/Design**: user experience, design systems, information architecture
- **Data**: analytics, dashboards, ETL, data migration
- **Compliance**: FedRAMP, FISMA, ATO, NIST
- **Modernization**: digital services, legacy systems, open source

## Project Structure

```
sam_gov/
├── config/
│   └── terms.yml              # Term definitions for scanning
├── data/
│   ├── samples/               # Downloaded extract files
│   ├── samples_json/          # Extracted JSON records
│   ├── samples_md/            # Markdown exports
│   ├── samples_report.json    # Discovery summary
│   ├── term_scan_report.json  # Term frequency analysis
│   └── top_matches_report.md  # Human-readable top matches
└── scripts/
    ├── explore_extracts.py    # Main discovery & extraction script
    └── analyze_matches.py     # Generate top matches report
```

## Data Schema

### Legacy FBO XML Fields

Extracted records contain:
- `DATE`: Day/month (MMDD format)
- `YEAR`: 2-digit year
- `AGENCY`: Federal agency name
- `OFFICE`: Sub-office or command
- `SOLNBR`: Solicitation number (unique ID)
- `SUBJECT`: Brief description
- `DESC`: Full description (long text)
- `NAICS`: Industry classification code
- `CLASSCOD`: Product/service classification
- `URL`: Original FBO/SAM.gov listing URL
- `CONTACT`: Point of contact with email/phone
- `RESPDATE`: Response due date (MMDDYY)
- `ARCHDATE`: Archive date (MMDDYYYY)
- `SETASIDE`: Small business set-aside type
- `POPCOUNTRY`, `POPADDRESS`, `POPZIP`: Place of performance

## Findings (25-File Sample)

### Top Terms by Frequency
1. **web** (295 matches)
2. **software** (74 matches)
3. **ux** (71 matches) - note: includes "UI" as user interface
4. **application** (46 matches)
5. **portal** (29 matches)
6. **modernization** (22 matches)

### Observations
- Legacy FBO XML extracts from 2019 are the primary format
- Most records are pre-solicitations (`<PRESOL>` tag)
- Attachment URLs appear in `URL` field, but ZIPs are rare in historical feed
- The `DATE` field is typically MMDD with separate `YEAR` field (e.g., `1025` + `19` = Oct 25, 2019)

## 🤖 Ollama Integration

### Requirements
- Ollama server running at http://localhost:11434/
- Model: `gpt-oss:20b` (or any compatible model)

### Quick Demo

Run the interactive demo to see Ollama analyze sample opportunities:

```bash
python demo_ollama.py
```

This will:
1. Summarize a sample opportunity
2. Extract technology keywords
3. Assess relevance for digital services companies

### Analyze Multiple Records

```bash
# Summarize top 5 opportunities
python scripts/ollama_analyzer.py \
  --input data/samples_json \
  --task summarize \
  --limit 5

# Extract technologies from all records
python scripts/ollama_analyzer.py \
  --input data/samples_json \
  --task extract_tech \
  --limit 10 \
  --output data/extracted_tech.json

# Classify opportunities by category
python scripts/ollama_analyzer.py \
  --input data/samples_json \
  --task classify \
  --limit 10 \
  --output data/classifications.json

# Assess relevance for your company
python scripts/ollama_analyzer.py \
  --input data/samples_json \
  --task assess_relevance \
  --limit 10 \
  --output data/relevance_scores.json
```

**Available tasks**:
- `summarize` - Generate 2-3 sentence summaries
- `extract_tech` - List all technology keywords
- `classify` - Categorize by domain (ICT, Web, Data, etc.)
- `assess_relevance` - Score relevance (0-10) for your company

### Interactive Requirements Clarification with Spec-kitty

Launch the interactive assistant to clarify ambiguous requirements:

```bash
python scripts/spec_kitty.py
```

**Features**:
- Ask clarifying questions about data schema, fields, and pipeline design
- Get 2-3 options with pros/cons for each decision
- Understand what breaks if assumptions are wrong
- Save conversation history with `/save <filename>`

**Single-Shot Mode**:

```bash
python scripts/spec_kitty.py \
  --prompt "Should I use SOLNBR or DATE+AGENCY as the unique ID?"
```

## 📅 Process Today's Opportunities/Wins

Process all SAM.gov records posted for a target date from the live `ContractOpportunitiesFullCSV.csv` feed.

```bash
# Strictly today's records
python scripts/process_today.py --target-date 2026-03-04

# If none exist for target date, automatically use latest available date
python scripts/process_today.py --target-date 2026-03-04 --fallback-latest

# Include Ollama relevance assessment
python scripts/process_today.py --target-date 2026-03-04 --fallback-latest --with-ollama
```

Outputs are written to:
- `data/today/summary.json`
- `data/today/opportunities.json`
- `data/today/wins.json`
- `data/today/relationships.json`
- `data/today/high_value_matches.json`
- `data/today/high_value_alert.md`
- `data/today/persistence_summary.json`
- `docs/data/today_summary.json` (for GitHub Pages)
- `docs/data/today_relationships.json` (for GitHub Pages)
- `docs/data/today_departments.json` (for GitHub Pages)

### Dedup + Persistence (SQLite)

```bash
python scripts/persist_to_sqlite.py
```

SQLite DB:
- `data/opportunities.sqlite`

Tracks:
- first seen date
- last seen date
- seen count
- per-day sightings

### High-Value Alert Generation

```bash
python scripts/generate_alerts.py --min-hits 8
```

Alert artifacts:
- `data/today/high_value_matches.json`
- `data/today/high_value_alert.md`
- `data/today/alerts_summary.json`

## 🌐 GitHub Pages Visualization

A static dashboard is available in `docs/` to visualize counts, term matches, top records, and relationships.

```bash
# refresh data first
python scripts/process_today.py --target-date 2026-03-04 --fallback-latest

# open locally (any static server)
python -m http.server 8000 --directory docs
```

Then open: `http://localhost:8000`

Dashboard features:
- notice type breakdown
- department-by-department breakdown (today's snapshot)
- top matching records
- agency/type/NAICS relationships

**Trends Page** (`docs/trends.html`):
- department activity over time
- sparkline charts of department posting patterns
- historical comparison of top agencies
- access via "View Trends →" button on main dashboard

To publish on GitHub Pages:
1. Push this repository to GitHub.
2. In repository settings, enable Pages with source: **Deploy from a branch**.
3. Select branch: `main`, folder: `/docs`.

## ⚙️ Daily Automation (GitHub Actions)

Workflow file: `.github/workflows/ingest.yml`

What it does daily:
1. Uses the current America/New_York date.
2. Runs `scripts/process_today.py --target-date <today> --fallback-latest`.
3. Runs dedup persistence to `data/opportunities.sqlite`.
4. Generates high-value alert files and opens a GitHub Issue when matches exist.
5. Commits and pushes updates when artifacts changed.

Manual trigger:
- GitHub → Actions → **Daily SAM.gov ingest** → **Run workflow**

## 🗓️ Weekly Historical Rebuild (GitHub Actions)

Workflow file: `.github/workflows/weekly-historical.yml`

What it does weekly:
1. Refreshes latest 25 historical extract samples.
2. Rebuilds `data/term_scan_report.json` from markdown samples.
3. Rebuilds `data/top_matches_report.md`.
4. Commits and pushes only if those artifacts changed.

Manual trigger:
- GitHub → Actions → **Weekly historical rebuild** → **Run workflow**

## 🤝 Agent Instructions

This repository includes an agent-focused guide in `AGENTS.md` (aligned with https://agents.md) for setup, workflows, conventions, and validation steps.

## Next Steps

1. **Ollama Analysis**: Use local LLM for schema inference, content summarization, and term extraction (✅ Complete)
2. **Spec-kitty Workflow**: Interactive clarification for ambiguous requirements
3. **PDF Processing**: Download attachments, convert to Markdown with pymupdf4llm
4. **Deduplication**: SQLite store keyed by `SOLNBR` or stable ID
5. **GitHub Actions**: Automated daily ingestion + commit to repo
6. **GitHub Pages**: Searchable site with JSON index for client-side search

## Configuration

### Terms (config/terms.yml)

Define search terms by category:
- `name`: Term identifier
- `patterns`: List of regex patterns
- `category`: Grouping (technology, accessibility, data, etc.)

### Options
- `case_sensitive`: false (ignore case)
- `word_boundary`: true (match whole words only)
- `allow_hyphens`: true (match hyphenated variants)

## Notes

- **Storage**: Keep markdown exports; do not commit large PDFs
- **Rate Limits**: SAM.gov API has no documented rate limit, but be respectful
- **Playwright**: Required for dynamic pages; headless Chromium renders JS
- **Ollama**: Local LLM server at http://localhost:11434/

## Resources

- SAM.gov Data Services: https://sam.gov/data-services/
- SAM.gov API (listfiles): https://sam.gov/api/prod/fileextractservices/v1/api/listfiles
- Open.gsa.gov: https://open.gsa.gov/api/
- Playwright Docs: https://playwright.dev/python/

## 🤖 AI Disclosure

This project uses AI tools for development, optional runtime analysis, and CI/CD automation. In the interest of transparency, here is a full disclosure of every AI tool used and its role.

### Development Assistance

- **GitHub Copilot**: Used as an AI coding assistant during the development of this project, including code generation, code review, documentation, and refactoring.
- **Claude (Anthropic)**: Used by the GitHub Copilot coding agent to implement features and changes in this repository (e.g., adding this AI disclosure section).

### Runtime AI (Optional — not enabled by default)

- **Ollama (local LLM, default model `gpt-oss:20b`)**: Used optionally for opportunity analysis tasks — summarization, technology extraction, classification, and relevance scoring. Activated by passing `--with-ollama` to `process_today.py`, or by running `scripts/ollama_analyzer.py` or `demo_ollama.py` directly. Requires a local Ollama server at `http://localhost:11434/`. Prompt usage is logged to `data/ollama_prompts.log`. **Not enabled in the default daily automation workflow.**
- **GitHub Models (default model `gpt-4o-mini`)**: Supported as an alternative cloud LLM provider for the same opportunity analysis tasks. Activated by passing `--llm-provider github` along with `--with-ollama`. Requires a `GITHUB_TOKEN` or `GITHUB_MODELS_TOKEN` environment variable. **Not enabled in the default daily automation workflow.**

### CI/CD Automation

- **GitHub Copilot Accessibility Scanner**: The `.github/workflows/a11y-scan.yml` workflow uses the `github/accessibility-scanner` action to scan the GitHub Pages dashboard for WCAG violations and file issues. The workflow is configured with `skip_copilot_assignment: false`, meaning detected issues may be assigned to GitHub Copilot for automated remediation via pull requests.

### Browser-Based AI

No browser-based AI is used in this application. The [Playwright](https://playwright.dev/python/) library is used exclusively for web scraping (rendering JavaScript-heavy SAM.gov pages) and does not incorporate any AI or LLM components.

### Updating This Disclosure

If you contribute to this project using AI tools, please update this section to accurately reflect which tools were used and in what capacity. See the [AGENTS.md](AGENTS.md) collaboration notes for guidance.

---

## Contributing

This is an open source project and constructive contributions are welcome and appreciated!

- **Repository**: [https://github.com/mgifford/sam_gov_md](https://github.com/mgifford/sam_gov_md)
- Report bugs or request features via [GitHub Issues](https://github.com/mgifford/sam_gov_md/issues)
- Submit improvements via [Pull Requests](https://github.com/mgifford/sam_gov_md/pulls)

## License

TBD
