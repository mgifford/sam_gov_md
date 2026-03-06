# LLM Usage Report & Cost Comparison

## 📊 Report Location

**Analysis Script**: `scripts/analyze_ollama_log.py`  
**Log File**: `data/ollama_prompts.log`  
**Run Report**: `python scripts/analyze_ollama_log.py`

---

## 🔍 Current Status

As of March 6, 2026:
- **Total prompts logged**: 1 (test query)
- **Local Ollama**: 1 prompt (100%)
- **GitHub Models (Copilot)**: 0 prompts (0%)
- **Cost**: $0.00

---

## 💡 Why So Few Entries?

LLM analysis is **opt-in** and currently **NOT enabled** in the daily automation workflow.

The `process_today.py` script supports LLM analysis but requires the `--with-ollama` flag:

```bash
# Manual run WITH LLM analysis
python scripts/process_today.py --target-date 2026-03-06 --with-ollama

# Manual run WITHOUT LLM analysis (current default)
python scripts/process_today.py --target-date 2026-03-06
```

**Daily automation** (.github/workflows/ingest.yml) runs WITHOUT the `--with-ollama` flag, so:
- No LLM analysis happens automatically
- Only basic data extraction and term matching occurs
- Prompts are only logged when LLM analysis is explicitly requested

---

## 🆚 Local Ollama vs GitHub Models (Copilot)

### Provider Comparison

| Feature | Local Ollama | GitHub Models (Copilot) |
|---------|-------------|------------------------|
| **Cost** | FREE (after setup) | ~$0.15/1M input tokens |
| **Speed** | Depends on hardware | Fast (cloud API) |
| **Privacy** | Fully local | Data sent to cloud |
| **Setup** | Requires local installation | Just needs API token |
| **Models** | gpt-oss:20b, llama3, etc. | gpt-4o-mini, gpt-4o |

### Cost Analysis (Future Projections)

If analyzing **1,500 opportunities per day** with LLM:

**Scenario 1: 100% Local Ollama**
- Cost per day: $0.00
- Cost per month: $0.00
- Cost per year: $0.00

**Scenario 2: 100% GitHub Models**
- Estimated ~500 tokens/opportunity
- 1,500 opps × 500 tokens = 750,000 tokens/day
- Cost per day: ~$0.11 (input) + ~$0.22 (output) = **~$0.33/day**
- Cost per month: ~$10
- Cost per year: ~$120

**Scenario 3: Hybrid (90% Ollama, 10% GitHub as fallback)**
- Cost per day: ~$0.03
- Cost per month: ~$1
- Cost per year: ~$12
- **Savings: 90%** vs. full cloud

---

## 📈 Report Features

When you run `python scripts/analyze_ollama_log.py`, you get:

1. **Provider Breakdown**: Local Ollama vs GitHub Models split
2. **Cost Analysis**: 
   - Actual costs incurred
   - Hypothetical costs if all were cloud
   - Savings from using local inference
3. **Task Breakdown**: What the LLM was used for (summarize, classify, etc.)
4. **Model Usage**: Which models were called (gpt-oss:20b, gpt-4o-mini, etc.)
5. **Timeline**: Prompts by date
6. **Recent Activity**: Last 5 prompts with previews

---

## ⚙️ How to Enable LLM Analysis

### Option 1: Manual Testing

```bash
cd /Users/mgifford/sam_gov
source .venv/bin/activate

# Run with local Ollama
python scripts/process_today.py --target-date 2026-03-06 --fallback-latest --with-ollama

# Run with GitHub Models
python scripts/process_today.py --target-date 2026-03-06 --fallback-latest \\
  --llm-provider github
```

### Option 2: Enable in Daily Automation

Edit `.github/workflows/ingest.yml`:

```yaml
- name: Process latest opportunities and wins
  run: |
    TARGET_DATE=$(TZ=America/New_York date +%F)
    echo "TARGET_DATE=$TARGET_DATE"
    python scripts/process_today.py --target-date "$TARGET_DATE" --fallback-latest --with-ollama
```

**Note**: This requires Ollama to be running on the GitHub Actions runner (not currently set up) OR using `--llm-provider github` with a token.

---

## 🎯 What LLM Analysis Provides

When enabled, LLM analysis adds:

1. **Opportunity Summaries**: 2-3 sentence descriptions of technical requirements
2. **Technology Extraction**: Automatic keyword detection beyond term matching
3. **Classification**: Categorize opportunities (ICT, Web, Data, Cybersecurity, etc.)
4. **Relevance Scoring**: Rate opportunities 0-10 for your company's focus areas
   - Web accessibility (Section 508, WCAG)
   - Drupal/CMS development
   - Digital government services
   - Open source solutions

Output saved to: `data/today/ollama_relevance.json`

---

## 📝 Current Implementation Details

**Logging Location**: Both providers log to the same file
- `ollama_analyzer.py` calls `log_prompt()` for every request
- Logs task type, model, token estimate, and prompt preview
- Format: JSONL (one JSON object per line)

**Task Types Tracked**:
- `generate` - Ollama direct generation
- `chat` - Ollama chat mode
- `github-chat` - GitHub Models chat
- `test` - Manual testing
- `summarize`, `extract_tech`, `classify`, `assess_relevance` - Analysis tasks

---

## 🚀 Recommendation

**For Production Use**:
1. Keep daily automation WITHOUT LLM analysis (current state)
   - Maintains fast, free processing
   - Focuses on term matching and data extraction
   
2. Run LLM analysis manually for high-value opportunities only
   ```bash
   # Filter to top 100 opportunities by your criteria first
   python scripts/process_today.py --target-date 2026-03-06 \\
     --with-ollama --llm-provider ollama
   ```

3. Use GitHub Models as fallback when Ollama unavailable
   - Set `GITHUB_TOKEN` environment variable
   - Use `--llm-provider github --llm-fallback`

**Cost Impact**: Current approach = $0/month, keeps it that way while preserving option for deep analysis when needed.
