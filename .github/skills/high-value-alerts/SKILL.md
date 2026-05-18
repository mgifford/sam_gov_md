---
name: high-value-alerts
description: "Generate high-value opportunity alert outputs and summaries. Use when user asks for top matches, alert thresholds, or refreshed docs/data alert intelligence."
---

# High-Value Alerts

## Purpose
Produce high-signal alert rows from processed opportunities, including top-match reporting for decision support.

## Use When
- User asks for high-value or high-hit opportunities.
- User asks to tune alert thresholds.
- User asks to regenerate alert outputs after new ingestion.

## Primary Commands
```bash
source .venv/bin/activate
python scripts/generate_alerts.py --min-hits 8
python scripts/analyze_matches.py
```

## Outputs
- `data/today/high_value_alerts.json`
- `data/top_matches_report.md`
- `docs/data/high_value_alerts.json` (when pipeline export includes docs publication)

## Validation
```bash
python -m pytest tests/test_generate_alerts.py tests/test_analyze_matches.py -q
```

## Notes
Keep thresholds deterministic and document any threshold changes in README.
