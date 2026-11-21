#!/usr/bin/env bash
# One-command reproduction (Git Bash / Linux / macOS). Needs ADAPTION_API_KEY in .env.
# All LLM calls are cached in cache/llm, so a rerun with a warm cache costs nothing.
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python}
mkdir -p data/raw
if ! ls data/raw/train-*.parquet >/dev/null 2>&1; then
  for i in $(seq 0 11); do
    curl -sL -o data/raw/train-$i.parquet \
      "https://huggingface.co/api/datasets/nebius/SWE-agent-trajectories/parquet/default/train/$i.parquet"
  done
fi
for c in python secrets; do
  [ -f configs/semgrep_$c.yml ] || curl -sL "https://semgrep.dev/c/p/$c" -o configs/semgrep_$c.yml
done
cd src
$PY load_data.py --n 420            # sample honest trajectories
$PY make_attacks.py                 # final reports + 224 attacks (A1-A7)
$PY validate_attacks.py             # automatic checks, hand-check sheet
$PY build_dataset.py                # dataset.jsonl + train/test/heldout splits
$PY tier0_static.py                 # semgrep + bandit + detect-secrets + regex
$PY tier1_saydo.py                  # cheap say-vs-do check
$PY tier2_judge.py                  # strong full-trajectory judge
$PY tier2_judge.py --ablation       # judge without trajectory
$PY backtest.py                     # metrics, CIs, plots -> results/
$PY error_analysis.py               # misses + false positives -> results/error_cases.md
# PDF report (optional: pip install -r requirements-report.txt)
if $PY -c "import reportlab" 2>/dev/null; then
  $PY report_figures.py && $PY make_report.py   # -> report/Say_vs_Do_report.pdf
fi
