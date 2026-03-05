# New Features: Prompt Logging & Dashboard Anchors

## 1. Ollama Prompt Logging

All prompts sent to Ollama (or GitHub Models) are now automatically logged to track usage over time.

### Usage

**View prompt log analysis:**
```bash
python scripts/analyze_ollama_log.py
```

This will show:
- Total prompts logged
- Prompts grouped by task type (generate, chat, github-chat)
- Prompts grouped by model
- Estimated token usage
- Prompts by date
- Latest 5 prompts as samples

**Log file location:** `data/ollama_prompts.log` (automatically created)

**Log format:** Each line is JSON with:
- `timestamp`: ISO format timestamp when prompt was sent
- `task`: Type of operation (generate, chat, github-chat)
- `model`: Model used
- `prompt_length`: Number of characters in the prompt
- `prompt_preview`: First 200 characters of the prompt for reference

**Note:** The log file is ignored by git (in `.gitignore`) so it won't be committed, making it safe to track locally.

### Example Log Analysis Output

```
📊 Ollama Prompt Log Analysis
==================================================
Total prompts logged: 245
Date range: 2026-02-28 to 2026-03-05

Prompts by task:
  - generate: 180
  - chat: 65

Prompts by model:
  - gpt-oss:20b: 245

Estimated token usage:
  - Total characters: 1,234,567
  - Estimated tokens: 308,641

Prompts by date:
  - 2026-02-28: 42 prompts
  - 2026-03-01: 38 prompts
  - 2026-03-02: 51 prompts
  - ...
```

## 2. Dashboard Anchor Links

The main SAM.gov dashboard now has clickable anchor links for easier sharing and navigation.

### Features

- **Table of Contents:** Links to all major sections
- **Shareable URLs:** Each section can be linked directly
  - `http://localhost:8000/#notice-breakdown`
  - `http://localhost:8000/#department-breakdown`
  - `http://localhost:8000/#awarded-companies`
  - `http://localhost:8000/#popular-terms`
  - `http://localhost:8000/#top-matches`
  - `http://localhost:8000/#relationships`

- **Automatic headings:** Opportunity pages (markdown) automatically get anchors from Jekyll

### Usage

1. Open the dashboard at `http://localhost:8000` (or your deployment URL)
2. Click any link in the "Table of Contents" section at the top
3. Share specific sections by copying the URL from the address bar

Examples:
- Link to Department Breakdown: `https://example.com/#department-breakdown`
- Link to Top Matches: `https://example.com/#top-matches`

## Implementation Details

### Prompt Logging

Modified files:
- `scripts/ollama_analyzer.py`: Added `log_prompt()` function and logging calls in:
  - `OllamaClient.generate()`
  - `OllamaClient.chat()`
  - `GitHubModelsClient.chat()`

### Dashboard Anchors

Modified files:
- `docs/index.html`: 
  - Added table of contents section
  - Added `id` attributes to all major section headings
  - Links follow format: `#section-name` (kebab-case)

### Gitignore

Modified:
- `.gitignore`: Added `data/ollama_prompts.log` to prevent committing logs
