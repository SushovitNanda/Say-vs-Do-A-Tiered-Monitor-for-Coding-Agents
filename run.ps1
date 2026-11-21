# One-command reproduction (Windows PowerShell). Needs ADAPTION_API_KEY in .env.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$py = if ($env:PY) { $env:PY } else { "python" }
New-Item -ItemType Directory -Force data/raw | Out-Null
if (-not (Test-Path data/raw/train-0.parquet)) {
  0..11 | ForEach-Object {
    Invoke-WebRequest -Uri "https://huggingface.co/api/datasets/nebius/SWE-agent-trajectories/parquet/default/train/$_.parquet" -OutFile "data/raw/train-$_.parquet"
  }
}
foreach ($c in "python","secrets") { if (-not (Test-Path "configs/semgrep_$c.yml")) { Invoke-WebRequest -Uri "https://semgrep.dev/c/p/$c" -OutFile "configs/semgrep_$c.yml" } }
Set-Location src
& $py load_data.py --n 420
& $py make_attacks.py
& $py validate_attacks.py
& $py build_dataset.py
& $py tier0_static.py
& $py tier1_saydo.py
& $py tier2_judge.py
& $py tier2_judge.py --ablation
& $py backtest.py
& $py error_analysis.py
# PDF report (optional: pip install -r requirements-report.txt)
& $py -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('reportlab') else 1)"
if ($LASTEXITCODE -eq 0) { & $py report_figures.py; & $py make_report.py }
