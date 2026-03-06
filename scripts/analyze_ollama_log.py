#!/usr/bin/env python3
"""
Analyze Ollama prompt log to track growth and patterns.
Includes cost comparison between local Ollama and GitHub Models (Copilot).
"""
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime


# GitHub Models pricing (approximate, as of March 2024)
# gpt-4o-mini: ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens
# Using conservative estimate for analysis
GITHUB_MODELS_COST_PER_1M_INPUT = 0.15
GITHUB_MODELS_COST_PER_1M_OUTPUT = 0.60


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
    
    # Separate by provider
    ollama_entries = [e for e in entries if 'github' not in e.get('task', '').lower()]
    github_entries = [e for e in entries if 'github' in e.get('task', '').lower()]
    
    # Statistics
    print(f"\n📊 LLM Usage Analysis Report")
    print(f"{'='*60}")
    print(f"Total prompts logged: {len(entries)}")
    print(f"Date range: {entries[0]['datetime'].date()} to {entries[-1]['datetime'].date()}")
    
    print(f"\n🔵 Provider Breakdown:")
    print(f"  Local Ollama:      {len(ollama_entries):4d} prompts ({len(ollama_entries)/len(entries)*100:5.1f}%)")
    print(f"  GitHub Models:     {len(github_entries):4d} prompts ({len(github_entries)/len(entries)*100:5.1f}%)")
    
    # Token usage estimates
    ollama_chars = sum(e['prompt_length'] for e in ollama_entries)
    github_chars = sum(e['prompt_length'] for e in github_entries)
    total_chars = ollama_chars + github_chars
    
    ollama_tokens = ollama_chars / 4  # rough estimate: 4 chars per token
    github_tokens = github_chars / 4
    total_tokens = total_chars / 4
    
    print(f"\n💰 Cost Analysis:")
    print(f"{'─'*60}")
    
    # Actual GitHub Models cost
    github_cost = (github_tokens / 1_000_000) * GITHUB_MODELS_COST_PER_1M_INPUT
    github_cost += (github_tokens / 1_000_000) * GITHUB_MODELS_COST_PER_1M_OUTPUT * 0.5  # assume 50% output tokens
    
    print(f"  Local Ollama:")
    print(f"    Prompts:         {len(ollama_entries):,}")
    print(f"    Est. tokens:     {ollama_tokens:,.0f}")
    print(f"    Cost:            $0.00 (FREE - local inference)")
    
    print(f"\n  GitHub Models (Copilot):")
    print(f"    Prompts:         {len(github_entries):,}")
    print(f"    Est. tokens:     {github_tokens:,.0f}")
    print(f"    Actual cost:     ${github_cost:.4f}")
    
    # What if ALL were done via GitHub Models
    hypothetical_cost = (total_tokens / 1_000_000) * GITHUB_MODELS_COST_PER_1M_INPUT
    hypothetical_cost += (total_tokens / 1_000_000) * GITHUB_MODELS_COST_PER_1M_OUTPUT * 0.5
    
    print(f"\n  💡 Cost Savings:")
    print(f"    If all via GitHub Models: ${hypothetical_cost:.4f}")
    print(f"    Using local Ollama:       ${github_cost:.4f}")
    print(f"    Savings:                  ${hypothetical_cost - github_cost:.4f}")
    print(f"    Savings:                  {(1 - github_cost/hypothetical_cost)*100 if hypothetical_cost > 0 else 0:.1f}%")
    
    # Group by task
    by_task = defaultdict(list)
    for entry in entries:
        by_task[entry['task']].append(entry)
    
    print(f"\n📋 Prompts by task:")
    for task, task_entries in sorted(by_task.items(), key=lambda x: -len(x[1])):
        provider = "GitHub" if "github" in task.lower() else "Ollama"
        print(f"  - {task:20s} {len(task_entries):4d} ({provider})")
    
    # Group by model
    by_model = Counter(e['model'] for e in entries)
    print(f"\n🤖 Prompts by model:")
    for model, count in by_model.most_common():
        print(f"  - {model:30s} {count:4d}")
    
    # By date
    by_date = defaultdict(list)
    for entry in entries:
        date = entry['datetime'].date()
        by_date[date].append(entry)
    
    print(f"\n📅 Prompts by date:")
    for date in sorted(by_date.keys()):
        ollama_count = len([e for e in by_date[date] if 'github' not in e.get('task', '').lower()])
        github_count = len([e for e in by_date[date] if 'github' in e.get('task', '').lower()])
        print(f"  - {date}: {len(by_date[date]):3d} prompts (Ollama: {ollama_count:3d}, GitHub: {github_count:3d})")
    
    # Show latest prompts
    print(f"\n📝 Latest 5 prompts:")
    for i, entry in enumerate(entries[-5:], 1):
        provider = "GitHub" if "github" in entry.get('task', '').lower() else "Ollama"
        print(f"  {i}. {entry['timestamp']} ({entry['task']}) - {entry['model']} [{provider}]")
        print(f"     Preview: {entry['prompt_preview'][:70]}...")


if __name__ == '__main__':
    analyze_prompts()
