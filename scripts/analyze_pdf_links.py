#!/usr/bin/env python3
"""Analyze PDF and document links in opportunity records."""
import json
from urllib.parse import urlparse

records = json.load(open('docs/data/today_records.json'))

pdf_links = []
other_doc_links = []
attachment_links = []

for record in records:
    additional = record.get('AdditionalInfoLink', '').strip()
    if additional:
        lower = additional.lower()
        if '.pdf' in lower:
            pdf_links.append({
                'id': record['NoticeId'],
                'url': additional,
                'title': record.get('Title', '')[:80]
            })
        elif any(x in lower for x in ['.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt']):
            other_doc_links.append({
                'id': record['NoticeId'],
                'url': additional
            })
        else:
            attachment_links.append({
                'id': record['NoticeId'],
                'url': additional
            })

print(f"PDF Links: {len(pdf_links)}")
print(f"Other Document Links (.docx, .xlsx, etc): {len(other_doc_links)}")
print(f"Other Attachment Links: {len(attachment_links)}")

print(f"\nSample PDF links:")
for item in pdf_links[:3]:
    print(f"  - {item['title'][:60]}")
    print(f"    {item['url'][:80]}")

print(f"\nDomain breakdown for PDF links:")
domains = {}
for item in pdf_links:
    parsed = urlparse(item['url'])
    domain = parsed.netloc or 'unknown'
    domains[domain] = domains.get(domain, 0) + 1

for domain, count in sorted(domains.items(), key=lambda x: -x[1])[:10]:
    print(f"  {domain}: {count}")
