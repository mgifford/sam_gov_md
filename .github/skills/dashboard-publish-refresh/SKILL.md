---
name: dashboard-publish-refresh
description: "Refresh docs/data payloads and verify GitHub Pages dashboard publishing artifacts. Use when user asks why pages are stale, missing rows, or not reflecting newest pipeline runs."
---

# Dashboard Publish Refresh

## Purpose
Rebuild and verify all dashboard-facing JSON artifacts under docs/data so GitHub Pages reflects current outputs.

## Use When
- User reports stale or empty dashboard pages.
- User asks to republish docs/data from fresh processing outputs.
- User asks to validate workflow artifact paths.

## Primary Commands
```bash
source .venv/bin/activate
python scripts/process_today.py --target-date YYYY-MM-DD --fallback-latest
python scripts/persist_to_sqlite.py
python scripts/generate_alerts.py --min-hits 8
python scripts/export_all_opportunities.py
python scripts/build_recompete_risk.py \
  --cohort dsc \
  --fy-start 2026-10-01 \
  --fy-end 2027-09-30 \
  --output-json data/today/recompetes.json \
  --output-docs-json docs/data/recompetes.json \
  --output-paracharts-spec docs/data/recompetes_paracharts_specs.json \
  --output-md data/today/summary.md
```

## Validation
```bash
jq 'length' docs/data/recompetes.json
jq 'length' docs/data/all_opportunities.json
python -m http.server 8000 --directory docs
```

## Notes
If recompete rows are empty, check date window and company match strategy first.
