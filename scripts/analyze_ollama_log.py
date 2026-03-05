#!/usr/bin/env python3
"""
Analyze Ollama prompt log to track growth and patterns.
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


def analyze_prompts():
    log_file = Path(__file__).parent.parent / 'data' / 'ollama_prompts.log'
    
    if not log_file.exists():
        print(f"No prompt log found at {log_file}")
        print("Run process_today.py to start logging prompts.")
        return
    
    entries = []
    with open(log_file) as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    
    if not entries:
        print("No prompt entries found in log.")
        return
    
    # Parse timestamps
    for entry in entries:
        entry['datetime'] = datetime.fromisoformat(entry['timestamp'])
    
    # Sort by timestamp
    entries.sort(key=lambda x: x['datetime'])
    
    # Statistics
    print(f"\n📊 Ollama Prompt Log Analysis")
    print(f"{'='*50}")
    print(f"Total prompts logged: {len(entries)}")
    print(f"Date range: {entries[0]['datetime'].date()} to {entries[-1]['datetime'].date()}")
    
    # Group by task
    by_task = defaultdict(list)
    for entry in entries:
        by_task[entry['task']].append(entry)
    
    print(f"\nPrompts by task:")
    for task, task_entries in sorted(by_task.items(), key=lambda x: -len(x[1])):
        print(f"  - {task}: {len(task_entries)}")
    
    # Group by model
    by_model = Counter(e['model'] for e in entries)
    print(f"\nPrompts by model:")
    for model, count in by_model.most_common():
        print(f"  - {model}: {count}")
    
    # Token usage estimate (rough: ~4 chars per token)
    total_chars = sum(e['prompt_length'] for e in entries)
    estimated_tokens = total_chars / 4
    print(f"\nEstimated token usage:")
    print(f"  - Total characters: {total_chars:,}")
    print(f"  - Estimated tokens: {estimated_tokens:,.0f}")
    
    # By date
    by_date = defaultdict(list)
    for entry in entries:
        date = entry['datetime'].date()
        by_date[date].append(entry)
    
    print(f"\nPrompts by date:")
    for date in sorted(by_date.keys()):
        print(f"  - {date}: {len(by_date[date])} prompts")
    
    # Show latest prompts
    print(f"\nLatest 5 prompts:")
    for i, entry in enumerate(entries[-5:], 1):
        print(f"  {i}. {entry['timestamp']} ({entry['task']}) - {entry['model']}")
        print(f"     Preview: {entry['prompt_preview'][:70]}...")


if __name__ == '__main__':
    analyze_prompts()
