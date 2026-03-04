#!/usr/bin/env python3
"""Demo: Analyze SAM.gov opportunities with Ollama."""

import json
import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from ollama_analyzer import OllamaClient

def main():
    print("=" * 80)
    print("SAM.gov Opportunity Analyzer with Ollama (gpt-oss:20b)")
    print("=" * 80)
    print()
    
    # Initialize client
    client = OllamaClient(model="gpt-oss:20b")
    
    # Health check
    if not client.health_check():
        print("✗ Ollama not running at http://localhost:11434")
        print("\nStart Ollama with: ollama serve")
        sys.exit(1)
    
    print("✓ Connected to Ollama")
    print(f"✓ Using model: {client.model}")
    print()
    
    # Load a sample record
    sample_dir = "data/samples_json"
    sample_files = sorted([f for f in os.listdir(sample_dir) if f.endswith(".sample.json")])
    
    if not sample_files:
        print("No sample JSON files found in data/samples_json/")
        sys.exit(1)
    
    # Pick the first sample with interesting content
    sample_path = None
    for fname in sample_files:
        path = os.path.join(sample_dir, fname)
        with open(path, "r") as f:
            record = json.load(f)
        # Look for records with substantial descriptions
        if record.get("DESC") and len(record.get("DESC", "")) > 500:
            sample_path = path
            break
    
    if not sample_path:
        sample_path = os.path.join(sample_dir, sample_files[0])
    
    with open(sample_path, "r") as f:
        record = json.load(f)
    
    print(f"Analyzing: {os.path.basename(sample_path)}")
    print("=" * 80)
    print(f"Solicitation: {record.get('SOLNBR', 'N/A')}")
    print(f"Agency: {record.get('AGENCY', 'N/A')}")
    print(f"Subject: {record.get('SUBJECT', 'N/A')}")
    print()
    
    # Task 1: Summarize
    print("Task 1: Summarize the opportunity")
    print("-" * 80)
    prompt = f"""Summarize this government contract opportunity in 2-3 sentences, focusing on technical requirements:

Agency: {record.get('AGENCY', 'N/A')}
Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:1500]}

Summary:"""
    
    summary = client.generate(prompt, stream=False)
    print(summary)
    print()
    
    # Task 2: Extract technologies
    print("Task 2: Extract technology keywords")
    print("-" * 80)
    prompt = f"""List all technology keywords and technical requirements mentioned in this contract. Format as a comma-separated list.

Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:1500]}

Technologies:"""
    
    tech = client.generate(prompt, stream=False)
    print(tech)
    print()
    
    # Task 3: Relevance assessment
    print("Task 3: Assess relevance for digital services company")
    print("-" * 80)
    prompt = f"""Rate this opportunity's relevance for a company specializing in:
- Web accessibility (Section 508, WCAG)
- Drupal/CMS development
- Digital government services
- Open source solutions

Score from 0-10 (10 = highly relevant) and explain why in 1-2 sentences.

Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:1200]}

Relevance Score and Reason:"""
    
    relevance = client.generate(prompt, stream=False)
    print(relevance)
    print()
    
    print("=" * 80)
    print("Demo complete!")
    print()
    print("Next steps:")
    print("1. Analyze multiple records:")
    print("   python scripts/ollama_analyzer.py --input data/samples_json --task summarize --limit 5")
    print()
    print("2. Interactive requirements clarification:")
    print("   python scripts/spec_kitty.py")
    print()
    print("3. Classify all opportunities:")
    print("   python scripts/ollama_analyzer.py --input data/samples_json --task classify --limit 10 --output data/classifications.json")


if __name__ == "__main__":
    main()
