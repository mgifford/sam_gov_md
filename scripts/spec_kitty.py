#!/usr/bin/env python3
"""Spec-kitty: Interactive requirements clarification assistant using Ollama."""

import argparse
import json
import sys
from typing import Optional

import requests


class SpecKitty:
    """Interactive requirements clarification agent."""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gpt-oss:20b"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.chat_url = f"{self.base_url}/api/chat"
        self.conversation = []
        
        self.system_prompt = """You are spec-kitty, an expert requirements analyst for government contract data pipelines.

Your job is to prevent bad assumptions by asking clarifying questions BEFORE implementation.

For each ambiguous requirement:
1. Present 2-3 plausible options
2. State your recommended default and explain why
3. Explain what will break if the assumption is wrong
4. Keep questions focused and actionable

Be concise and technical. Ask only blocking questions that affect implementation."""
    
    def health_check(self) -> bool:
        """Check if Ollama is running."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False
    
    def chat(self, user_message: str, stream: bool = True) -> Optional[str]:
        """Send a message and get a response."""
        # Add system prompt on first message
        if not self.conversation:
            self.conversation.append({
                "role": "system",
                "content": self.system_prompt
            })
        
        self.conversation.append({
            "role": "user",
            "content": user_message
        })
        
        try:
            payload = {
                "model": self.model,
                "messages": self.conversation,
                "stream": stream,
            }
            resp = requests.post(self.chat_url, json=payload, timeout=120)
            resp.raise_for_status()
            
            full_response = ""
            if stream:
                for line in resp.iter_lines():
                    if line:
                        chunk = json.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            content = chunk["message"]["content"]
                            full_response += content
                            if not chunk.get("done", False):
                                print(content, end="", flush=True)
                print()
            else:
                data = resp.json()
                full_response = data.get("message", {}).get("content", "")
                print(full_response)
            
            # Add assistant response to conversation
            self.conversation.append({
                "role": "assistant",
                "content": full_response
            })
            
            return full_response
        except Exception as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return None
    
    def save_conversation(self, filepath: str):
        """Save conversation history."""
        with open(filepath, "w") as f:
            json.dump(self.conversation, f, indent=2)
        print(f"\nConversation saved to {filepath}")
    
    def run_interactive(self):
        """Run interactive clarification session."""
        print("=" * 80)
        print("Spec-kitty: Requirements Clarification Assistant")
        print("=" * 80)
        print("\nCommands:")
        print("  /save <file>  - Save conversation")
        print("  /quit or /q   - Exit")
        print("  /help         - Show this help")
        print("\n" + "=" * 80 + "\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.startswith("/"):
                    cmd_parts = user_input.split(maxsplit=1)
                    cmd = cmd_parts[0].lower()
                    
                    if cmd in ["/quit", "/q"]:
                        print("\nGoodbye!")
                        break
                    elif cmd == "/help":
                        print("\nCommands: /save <file>, /quit, /help")
                        continue
                    elif cmd == "/save":
                        filepath = cmd_parts[1] if len(cmd_parts) > 1 else "conversation.json"
                        self.save_conversation(filepath)
                        continue
                    else:
                        print(f"Unknown command: {cmd}")
                        continue
                
                print("\nspec-kitty: ", end="")
                self.chat(user_input, stream=True)
                print()
                
            except KeyboardInterrupt:
                print("\n\nInterrupted. Use /quit to exit.")
            except EOFError:
                break


def main():
    parser = argparse.ArgumentParser(description="Spec-kitty: Interactive requirements clarification")
    parser.add_argument("--model", default="gpt-oss:20b", help="Ollama model")
    parser.add_argument("--base-url", default="http://localhost:11434", help="Ollama base URL")
    parser.add_argument("--prompt", help="Single prompt mode (non-interactive)")
    parser.add_argument("--context", help="Context file (JSON with sample data)")
    
    args = parser.parse_args()
    
    kitty = SpecKitty(base_url=args.base_url, model=args.model)
    
    if not kitty.health_check():
        print(f"Error: Ollama not running at {args.base_url}", file=sys.stderr)
        print("Start with: ollama serve", file=sys.stderr)
        sys.exit(1)
    
    if args.prompt:
        # Single-shot mode
        context = ""
        if args.context:
            with open(args.context, "r") as f:
                context = f"\n\nContext:\n{f.read()}"
        
        full_prompt = args.prompt + context
        print("spec-kitty: ", end="")
        kitty.chat(full_prompt, stream=True)
    else:
        # Interactive mode
        kitty.run_interactive()


if __name__ == "__main__":
    main()
