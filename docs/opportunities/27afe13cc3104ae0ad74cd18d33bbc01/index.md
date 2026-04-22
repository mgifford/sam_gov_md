---
layout: default
title: Data Web Access Subscription
agency: TREASURY, DEPARTMENT OF THE
notice_type: Sources Sought
notice_id: 27afe13cc3104ae0ad74cd18d33bbc01
---

# Data Web Access Subscription

- Agency: TREASURY, DEPARTMENT OF THE
- Type: Sources Sought
- Posted: 2026-04-20 11:32:33.431-04
- Solicitation Number: 26-18-APMO

## Summary

The Large Business & International division of IRS is looking for a curated global company database with integrated research tools and a suite of database subscriptions to enable tax audit, analysis, and potential tax assessments in the area of Section 482 transfer pricing and international taxation. The IRS is seeking full access allowing users to easily export all relevant information, save analyses, search sets for future use, and provide future enhancements/updates to the government at no additional cost. RFI due date is extended until 4/24/2026 4:00PM EST.

## Contacts

- Primary Contact:
  - Name: Ana Rollins
  - Email: analeatha.s.rollins@irs.gov
- Secondary Contact:
  - Name: Iman Street
  - Email: iman.street@irs.gov

## Links

- [SAM.gov opportunity page](https://sam.gov/workspace/contract/opp/27afe13cc3104ae0ad74cd18d33bbc01/view)

---

## 🔍 Debugging: Attachment Extraction Status

This section explains why the PDF and spreadsheet attachments listed on SAM.gov are **not shown** on this page.

### What SAM.gov shows

SAM.gov lists 3 attachments for this opportunity:

| File | Size | Visibility | Posted |
|------|------|------------|--------|
| RFI - Data Web Access Subscription 4.20.26.pdf | 231 KB | Public | Apr 20, 2026 |
| Attachment 2 - Vendor Response Form.xlsx | 139 KB | Public | Apr 8, 2026 |
| Attachment 1 - DWAS Requirement Document.pdf | 277 KB | Public | Apr 8, 2026 |

### Why the content is missing

**Step 1 — CSV row has no `AdditionalInfoLink`.**
The SAM.gov full CSV extract (`ContractOpportunitiesFullCSV.csv`) populates an `AdditionalInfoLink` column when a direct URL to a document is available. For this opportunity the column is blank, so the scraper had no direct link to follow.

**Step 2 — `AttachmentCount` in the processed record is 0.**
After `process_today.py` parsed the CSV row, `AttachmentCount` was recorded as `0` and `Attachments` as `[]`. The CSV does not carry individual attachment file IDs; those are only available via the SAM.gov REST API (`/opportunities/v1/noticedesc`).

**Step 3 — Not selected as one of the top-50 PDF extraction candidates.**
`scrape_opportunities.py` runs with `--limit 50` (see `.github/workflows/weekly-pdf-extraction.yml`). The selection function (`select_candidates`) places opportunities **with** an `AdditionalInfoLink` first. Since this opportunity has no link, it competes in the "without links" bucket ordered by posted date. With 73,563 rows in the CSV at the time of the last run, this opportunity was not reached within the 50-candidate window.

**Step 4 — No `pdf_content.md` was written.**
Because the opportunity was never processed by the scraper, no `pdf_content.md` file exists at:
```
docs/opportunities/27afe13cc3104ae0ad74cd18d33bbc01/pdf_content.md
```

### Pipeline summary

| Check | Status |
|-------|--------|
| Opportunity page (`index.md`) | ✅ Written |
| `AdditionalInfoLink` in CSV | ❌ Empty |
| In PDF extraction candidates (top 50) | ❌ Not selected |
| `pdf_content.md` exists | ❌ Missing |
| SAM.gov API queried for attachment IDs | ❌ Not reached |

### How to fix

Run `scrape_opportunities.py` targeting this specific notice ID, or increase `--limit` so this opportunity falls within the candidate window. A `SAM_API_KEY` is required for API-based attachment discovery:

```sh
python scripts/scrape_opportunities.py \
  --csv data/ContractOpportunitiesFullCSV.csv \
  --limit 500 \
  --api-key "$SAM_API_KEY"
```

Once the scraper processes this opportunity it will write `pdf_content.md` next to this file and add an **Extracted Documents** link above.