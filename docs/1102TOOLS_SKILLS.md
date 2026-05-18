# 1102tools Skills Integration

This project now includes a local skills catalog for the 1102tools federal contracting skills set.

Catalog file:
- config/skills/1102tools_skills_catalog.json

Workspace skill files:
- .github/skills/recompete-discovery/SKILL.md
- .github/skills/high-value-alerts/SKILL.md
- .github/skills/usaspending-enrichment/SKILL.md
- .github/skills/dashboard-publish-refresh/SKILL.md

## Included Skills

- ot-project-description-builder
- sow-pws-builder
- igce-builder-ffp
- igce-builder-lh-tm
- igce-builder-cr
- ot-cost-analysis

## Recompete Discovery Mapping

- Discovery framing: ot-project-description-builder
- Pre-solicitation drafting: sow-pws-builder
- Price strategy: igce-builder-ffp, igce-builder-lh-tm, igce-builder-cr
- Acquisition planning support: ot-cost-analysis

## MCP Notes

The upstream skills are designed to run with MCP servers (for example bls-oews, gsa-calc, gsa-perdiem).
This repository currently runs without those MCP dependencies for core recomplete extraction.
Use the catalog as a routing and implementation guide, then connect MCP tooling in your runtime when available.
