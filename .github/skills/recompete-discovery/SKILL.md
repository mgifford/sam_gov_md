---
name: recompete-discovery
description: "Build and refresh recompete risk outputs for contractor cohorts. Use when user asks for recompete discovery, expiring awards, Rule-of-Two screening, benchmark deltas, or docs/data/recompetes.json updates."
---

# Recompete Discovery

## Purpose
Generate recompete risk outputs for a selected company cohort using USASpending data, benchmark overlays, and Rule-of-Two evidence.

## Use When
- User asks to refresh recompete data for DSC, AI vendors, or a custom company list.
- User asks for expiring contract opportunities in a specific date window.
- User asks to update the GitHub Pages recompete dashboard feed.

## Primary Commands
```bash
source .venv/bin/activate
python scripts/build_recompete_risk.py \
  --cohort dsc \
  --fy-start 2026-10-01 \
  --fy-end 2027-09-30 \
  --max-pages-per-company 8 \
  --output-json data/today/recompetes.json \
  --output-docs-json docs/data/recompetes.json \
  --output-paracharts-spec docs/data/recompetes_paracharts_specs.json \
  --output-md data/today/summary.md
```

## Common Variants
- Use a wider history window by changing `--fy-start`.
- Use `--cohort ai` for AI-focused vendors.
- Use `--benchmark-mode fallback` when external benchmark endpoints are unstable.

## Outputs
- `data/today/recompetes.json`
- `data/today/summary.md`
- `docs/data/recompetes.json`
- `docs/data/recompetes_paracharts_specs.json`

## Validation
```bash
python -m pytest tests/test_build_recompete_risk.py -q
jq 'length' docs/data/recompetes.json
```
