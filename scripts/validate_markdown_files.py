#!/usr/bin/env python3
"""Validate that all markdown files referenced in the dashboard actually exist."""
import json
from pathlib import Path
from collections import defaultdict

def validate_markdown_files():
    """Check if all markdown files exist and have content."""
    docs_dir = Path('docs')
    records_file = docs_dir / 'data' / 'today_records.json'
    
    if not records_file.exists():
        print(f"Error: {records_file} not found")
        return
    
    records = json.load(open(records_file))
    
    # Check each record's markdown file
    missing = []
    empty = []
    valid = []
    
    for record in records:
        notice_id = record.get('NoticeId', '').strip()
        if not notice_id:
            continue
        
        md_file = docs_dir / 'opportunities' / notice_id / 'index.md'
        
        if not md_file.exists():
            missing.append(notice_id)
        else:
            content = md_file.read_text(encoding='utf-8').strip()
            if not content:
                empty.append(notice_id)
            else:
                valid.append(notice_id)
    
    # Report
    print(f"\n📊 Markdown File Validation Report")
    print(f"{'='*50}")
    print(f"Total records: {len(records)}")
    print(f"✅ Valid markdown files: {len(valid)}")
    print(f"⚠️  Missing markdown files: {len(missing)}")
    print(f"❌ Empty markdown files: {len(empty)}")
    
    if missing:
        print(f"\nFirst 10 missing markdown files:")
        for notice_id in missing[:10]:
            print(f"  - {notice_id}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")
    
    if empty:
        print(f"\nEmpty markdown files:")
        for notice_id in empty:
            print(f"  - {notice_id}")
    
    # Check specific file if provided
    print(f"\nSpecific file check:")
    test_id = "09b5c4fe290147729a4f541e72095a6a"
    test_file = docs_dir / 'opportunities' / test_id / 'index.md'
    if test_file.exists():
        content = test_file.read_text(encoding='utf-8')
        print(f"✅ {test_id}/index.md exists")
        print(f"   Size: {len(content)} bytes")
        print(f"   Lines: {len(content.splitlines())}")
        # Check front matter
        if content.startswith('---'):
            lines = content.splitlines()
            end_matter = -1
            for i, line in enumerate(lines[1:], 1):
                if line == '---':
                    end_matter = i
                    break
            if end_matter > 0:
                print(f"   ✅ Valid Jekyll front matter")
            else:
                print(f"   ❌ Invalid Jekyll front matter (no closing ---)")
        else:
            print(f"   ❌ Missing Jekyll front matter")
    else:
        print(f"❌ {test_id}/index.md does not exist")
    
    # Suggestions
    if len(missing) > 0 or len(empty) > 0:
        print(f"\n💡 Suggestions:")
        print(f"  1. Run: python scripts/process_today.py --target-date 2026-03-05 --fallback-latest")
        print(f"  2. Verify all files were written to docs/opportunities/*/index.md")
        print(f"  3. Check GitHub Pages workflow (Actions tab) to ensure Jekyll build succeeded")

if __name__ == '__main__':
    validate_markdown_files()
