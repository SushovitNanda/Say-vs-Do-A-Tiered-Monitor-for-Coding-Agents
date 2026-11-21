"""Tier 1: the say-vs-do check with a cheap model.

Input: issue, final report and patch (NOT the trajectory). The model lists each
change, marks whether it is mentioned / needed / risky, and returns a 0-100
suspicion score.

Usage: python tier1_saydo.py [--model MODEL_ID]   (default: the `tier1` role)
"""
from __future__ import annotations

import argparse

from common import fill, load_prompt, truncate_middle
from monitor_utils import run_monitor

T = load_prompt("tier1_saydo")


def build(rec):
    return fill(T, issue=truncate_middle(rec["issue"], 8000), report=rec["final_report"],
                patch=truncate_middle(rec["patch"], 30000))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None, help="override model (writes tier1_<model>.jsonl)")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    if a.model:
        run_monitor("tier1", a.model, build, workers=a.workers, out_name=f"tier1_{a.model}")
    else:
        run_monitor("tier1", "tier1", build, workers=a.workers)
