---
name: usaspending-enrichment
description: "Refresh USASpending enrichment artifacts (vendor landscape, trends, and contract officer intelligence). Use when user asks for market intelligence context or enrichment reruns."
---

# USASpending Enrichment

## Purpose
Enrich core opportunity signals with historical contract intelligence from USASpending and related analysis scripts.

## Use When
- User asks for vendor landscape context around alerts.
- User asks for trends, officer extracts, or department-level forecasting updates.
- User asks to rerun enrichment after ingestion.

## Primary Commands
```bash
source .venv/bin/activate
python scripts/enrich_usaspending.py
python scripts/export_trends.py
python scripts/extract_contract_officers.py
python scripts/department_forecasting.py
```

## Outputs
- `docs/data/department_trends.json`
- `docs/data/contract_officers.json`
- `docs/data/department_forecasting.json`
- Additional enrichment artifacts under `data/today/`

## Validation
```bash
python -m pytest \
  tests/test_enrich_usaspending.py \
  tests/test_export_trends.py \
  tests/test_extract_contract_officers.py \
  tests/test_department_forecasting.py -q
```
