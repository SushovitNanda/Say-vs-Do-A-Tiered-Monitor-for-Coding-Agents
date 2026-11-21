"""Stretch: upload the training CSV to Adaption and launch AutoScientist LoRA runs.

Usage:
  python ft_launch.py launch --file train_core.csv --name core [--aug 1000] [--model Qwen/Qwen3.5-4B]
  python ft_launch.py status
  python ft_launch.py download --name core
Run metadata is kept in data/ft/runs.json.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from dotenv import load_dotenv

from common import DATA, ROOT

load_dotenv(ROOT / ".env")
from adaption import Adaption  # noqa: E402

FT_DIR = DATA / "ft"
RUNS = FT_DIR / "runs.json"


def load_runs():
    return json.loads(RUNS.read_text()) if RUNS.exists() else {}


def save_runs(r):
    RUNS.write_text(json.dumps(r, indent=2, default=str))


def launch(file: str, name: str, aug: int, model: str, iters: int, dataset_id: str | None = None):
    c = Adaption()
    if not dataset_id:
        ds = c.datasets.upload_file(str(FT_DIR / file), processing_mode="raw",
                                    column_mapping={"prompt": "prompt", "completion": "completion"})
        dataset_id = ds.dataset_id
        print("uploaded dataset", dataset_id)
    c.datasets.wait_for_completion(dataset_id)
    print("dataset ready")
    # column mapping is inferred: the raw upload already canonicalised prompt/completion
    kw = dict(dataset_id=dataset_id, model=model, training_method="instruction", max_iterations=iters)
    if aug:
        kw["augmentation_domain_rows"] = aug
    run = c.autoscientist.create(**kw)
    print("run", run.id, run.status, run.model)
    runs = load_runs()
    runs[name] = {"run_id": run.id, "dataset_id": dataset_id, "file": file, "aug": aug, "model": run.model,
                  "launched": time.time(), "status": run.status}
    save_runs(runs)


def status():
    c = Adaption()
    runs = load_runs()
    for name, r in runs.items():
        run = c.autoscientist.get(r["run_id"])
        r.update({"status": run.status, "iterations_completed": run.iterations_completed,
                  "best_win_rate": run.best_win_rate, "download_available": run.download_available,
                  "error": run.error,
                  "best_hyperparams": run.best_hyperparams.model_dump() if run.best_hyperparams else None})
        print(f"{name}: {run.status} iters={run.iterations_completed}/{run.max_iterations} "
              f"win={run.best_win_rate} download={run.download_available} err={run.error}")
    save_runs(runs)


def download(name: str):
    c = Adaption()
    r = load_runs()[name]
    out = ROOT.parent / "models" / f"ft_{name}.tgz"  # outside the repo (large), inside Apollo_Control
    out.parent.mkdir(parents=True, exist_ok=True)
    with c.autoscientist.with_streaming_response.download(r["run_id"]) as resp:
        resp.stream_to_file(str(out))
    print("downloaded", out, out.stat().st_size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["launch", "status", "download"])
    ap.add_argument("--file", default="train_fresh.csv")
    ap.add_argument("--name", default="core")
    ap.add_argument("--aug", type=int, default=0)
    ap.add_argument("--model", default="Qwen/Qwen3.5-4B")
    ap.add_argument("--iters", type=int, default=2)
    ap.add_argument("--dataset-id", default=None)
    a = ap.parse_args()
    if a.cmd == "launch":
        launch(a.file, a.name, a.aug, a.model, a.iters, a.dataset_id)
    elif a.cmd == "status":
        status()
    else:
        download(a.name)
