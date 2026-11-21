# Say-vs-Do-A-Tiered-Monitor-for-Coding-Agents
Build and backtest a cheap-to-expensive monitoring cascade that catches coding agents that insert flaws into code and hide them in what they report.

> Status: work in progress. See `PROJECT_PLAN.md` for the full plan.

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # add ADAPTION_API_KEY (and optionally OPENROUTER_API_KEY, HF_TOKEN)
python src/llm.py       # smoke test: one call per role model
```

Models and prices per role live in `configs/models.yaml`. `src/llm.py` wraps Adaption's
OpenAI-compatible endpoint (with OpenRouter as a fallback), with retries, a client-side rate limiter,
an on-disk cache and per-call logging of tokens, latency and cost.
