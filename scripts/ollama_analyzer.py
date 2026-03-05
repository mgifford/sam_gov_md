#!/usr/bin/env python3
"""Analyze SAM.gov opportunities using local Ollama LLM."""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests


# Global prompt log file path
PROMPT_LOG_FILE = Path(__file__).parent.parent / 'data' / 'ollama_prompts.log'


def log_prompt(task: str, prompt: str, model: str) -> None:
    """Log a prompt to a file for tracking and analysis."""
    try:
        PROMPT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().isoformat()
        log_entry = {
            'timestamp': timestamp,
            'task': task,
            'model': model,
            'prompt_length': len(prompt),
            'prompt_preview': prompt[:200]  # First 200 chars for reference
        }
        with open(PROMPT_LOG_FILE, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        print(f"Warning: Could not log prompt: {e}", file=sys.stderr)


class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gpt-oss:20b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.generate_url = f"{self.base_url}/api/generate"
        self.chat_url = f"{self.base_url}/api/chat"
        self.provider = "ollama"
        
    def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> list[str]:
        """List available models."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
        except Exception as exc:
            print(f"Error listing models: {exc}", file=sys.stderr)
            return []
    
    def generate(self, prompt: str, stream: bool = False) -> Optional[str]:
        """Generate completion using Ollama."""
        try:
            # Log the prompt
            log_prompt('generate', prompt, self.model)
            
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": stream,
            }
            resp = requests.post(self.generate_url, json=payload, timeout=120)
            resp.raise_for_status()
            
            if stream:
                # Handle streaming response
                full_response = ""
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "response" in chunk:
                            full_response += chunk["response"]
                            if not chunk.get("done", False):
                                print(chunk["response"], end="", flush=True)
                print()  # newline after streaming
                return full_response
            else:
                data = resp.json()
                return data.get("response", "")
        except Exception as exc:
            print(f"Error generating response: {exc}", file=sys.stderr)
            return None
    
    def chat(self, messages: list[dict], stream: bool = False) -> Optional[str]:
        """Chat completion using Ollama."""
        try:
            # Log the last user message as the prompt
            if messages:
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        log_prompt('chat', msg.get('content', ''), self.model)
                        break
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": stream,
            }
            resp = requests.post(self.chat_url, json=payload, timeout=120)
            resp.raise_for_status()
            
            if stream:
                full_response = ""
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            full_response += content
                            if not chunk.get("done", False):
                                print(content, end="", flush=True)
                print()
                return full_response
            else:
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except Exception as exc:
            print(f"Error in chat: {exc}", file=sys.stderr)
            return None


class GitHubModelsClient:
    def __init__(
        self,
        base_url: str = "https://models.inference.ai.azure.com",
        model: str = "gpt-4o-mini",
        token: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.provider = "github-models"
        self.token = token or os.getenv("GITHUB_MODELS_TOKEN") or os.getenv("GITHUB_TOKEN")

    def is_configured(self) -> bool:
        return bool(self.token)

    def chat(self, messages: list[dict], stream: bool = False) -> Optional[str]:
        if not self.token:
            print("Missing GitHub Models token. Set GITHUB_MODELS_TOKEN or GITHUB_TOKEN.", file=sys.stderr)
            return None
        try:
            # Log the last user message as the prompt
            if messages:
                for msg in reversed(messages):
                    if msg.get('role') == 'user':
                        log_prompt('github-chat', msg.get('content', ''), self.model)
                        break
            
            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.2,
                "stream": stream,
            }
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                headers=headers,
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
            choices = data.get("choices", [])
            if not choices:
                return None
            return choices[0].get("message", {}).get("content", "")
        except Exception as exc:
            print(f"Error in GitHub Models chat: {exc}", file=sys.stderr)
            return None


def analyze_record(client: OllamaClient | GitHubModelsClient, record: dict, task: str = "summarize") -> Optional[str]:
    """Analyze a single record using an LLM client."""
    
    if task == "summarize":
        prompt = f"""Summarize this government contract opportunity in 2-3 sentences, focusing on the technical requirements:

Agency: {record.get('AGENCY', 'N/A')}
Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:2000]}

Summary:"""
        return _dispatch_prompt(client, prompt)
    
    elif task == "extract_tech":
        prompt = f"""List all technology keywords and requirements mentioned in this contract opportunity. Format as a comma-separated list.

Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:2000]}

Technologies:"""
        return _dispatch_prompt(client, prompt)
    
    elif task == "classify":
        prompt = f"""Classify this contract opportunity into ONE of these categories:
- ICT/Software Development
- Web Services
- Data/Analytics
- eLearning/Training
- Infrastructure/Cloud
- Cybersecurity
- Other

Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:1000]}

Category:"""
        return _dispatch_prompt(client, prompt)
    
    elif task == "assess_relevance":
        prompt = f"""Rate this opportunity's relevance for a company specializing in:
- Web accessibility (Section 508, WCAG)
- Drupal/CMS development
- Digital government services
- Open source solutions

Score from 0-10 (10 = highly relevant) and explain why in one sentence.

Subject: {record.get('SUBJECT', 'N/A')}
Description: {record.get('DESC', 'N/A')[:1500]}

Relevance Score and Reason:"""
        return _dispatch_prompt(client, prompt)
    
    return None


def _dispatch_prompt(client: OllamaClient | GitHubModelsClient, prompt: str) -> Optional[str]:
    if getattr(client, "provider", "") == "github-models":
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        return client.chat(messages)
    return client.generate(prompt)


def main():
    parser = argparse.ArgumentParser(description="Analyze SAM.gov opportunities with Ollama")
    parser.add_argument("--model", default="gpt-oss:20b", help="Ollama model to use")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--task", choices=["summarize", "extract_tech", "classify", "assess_relevance"],
                        default="summarize", help="Analysis task")
    parser.add_argument("--input", required=True, help="Input JSON file or directory")
    parser.add_argument("--output", help="Output JSON file for results")
    parser.add_argument("--limit", type=int, default=5, help="Max records to process")
    parser.add_argument("--stream", action="store_true", help="Stream responses")
    
    args = parser.parse_args()
    
    client = OllamaClient(base_url=args.base_url, model=args.model)
    
    # Health check
    if not client.health_check():
        print(f"Error: Ollama not running at {args.base_url}", file=sys.stderr)
        print("Start Ollama with: ollama serve", file=sys.stderr)
        sys.exit(1)
    
    print(f"Connected to Ollama at {args.base_url}")
    models = client.list_models()
    print(f"Available models: {', '.join(models)}")
    
    if args.model not in models:
        print(f"Warning: Model '{args.model}' not found. Pull it with: ollama pull {args.model}")
        sys.exit(1)
    
    # Load input records
    input_path = Path(args.input)
    records = []
    
    if input_path.is_file():
        with open(input_path, "r") as f:
            records.append(json.load(f))
    elif input_path.is_dir():
        for file in sorted(input_path.glob("*.sample.json"))[:args.limit]:
            with open(file, "r") as f:
                record = json.load(f)
                record["_source_file"] = file.name
                records.append(record)
    else:
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)
    
    print(f"\nProcessing {len(records)} records with task: {args.task}\n")
    
    results = []
    for idx, record in enumerate(records[:args.limit], start=1):
        solnbr = record.get("SOLNBR", "unknown")
        subject = record.get("SUBJECT", "")[:60]
        print(f"\n[{idx}/{len(records)}] {solnbr}: {subject}")
        print("-" * 80)
        
        result = analyze_record(client, record, task=args.task)
        
        if result:
            if not args.stream:
                print(result)
            results.append({
                "solnbr": solnbr,
                "subject": record.get("SUBJECT"),
                "agency": record.get("AGENCY"),
                "url": record.get("URL"),
                "task": args.task,
                "result": result.strip(),
            })
    
    # Save results
    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\n\nResults saved to {args.output}")
    
    print(f"\n✓ Processed {len(results)} records")


if __name__ == "__main__":
    main()
