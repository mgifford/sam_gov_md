# GitHub Copilot Instructions

## Primary reference

All agent and contributor guidance is maintained in **[AGENTS.md](../AGENTS.md)** at the repository root. Read it first — it covers:

- Project overview and purpose (SAM.gov contract opportunity ingestion + GitHub Pages dashboard)
- Environment setup (`python3 -m venv`, dependency installation, Playwright)
- Core workflow commands (`process_today.py`, `persist_to_sqlite.py`, `generate_alerts.py`, `scan_terms.py`, `analyze_matches.py`)
- Automation overview (daily `ingest.yml` and weekly `weekly-pdf-extraction.yml` GitHub Actions workflows)
- Coding conventions (idempotent scripts, deterministic JSON outputs, no external services for core ingestion)
- Testing and validation steps
- Data and safety considerations (no secrets, public SAM.gov data only)
- Collaboration notes (root-cause fixes, minimal changes, update README.md and workflows for new outputs)

## Accessibility

When modifying any user-facing pages in `docs/` (dashboard, search, trends, opportunity pages) or project documentation, follow the guidelines in **[ACCESSIBILITY.md](../ACCESSIBILITY.md)**. Key requirements include:

- Target **WCAG 2.2 Level AA** conformance for all GitHub Pages output under `docs/`.
- Use semantic HTML, proper `alt` text, visible labels for form controls, and keyboard-accessible interactive elements.
- SVG visualizations must include an accessible `<title>` and `aria-labelledby`; provide a text/table fallback where practical.
- Automated axe-core scanning runs via `.github/workflows/a11y-scan.yml`; run `axe-cli` locally against `python -m http.server 8000 --directory docs` to check changes before pushing.

## Quick-start for a new coding agent

1. Read `AGENTS.md` (project structure, commands, conventions).
2. Read `ACCESSIBILITY.md` if touching `docs/` or any `*.md` documentation.
3. Activate the Python virtual environment: `source .venv/bin/activate`.
4. Make the smallest change that fixes the problem; keep scripts idempotent and outputs reproducible.
5. Validate with the targeted checks listed in `AGENTS.md § Testing and validation`.

## Errors and workarounds

Document any errors or non-obvious workarounds here so future agents can benefit:

<!-- Add entries in the format below as they are discovered:
### <Short error description> (YYYY-MM-DD)
**Symptom:** …
**Cause:** …
**Workaround / fix:** …
-->
