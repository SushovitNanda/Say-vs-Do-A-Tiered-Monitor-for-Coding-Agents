"""Tier 2: strong full-trajectory judge.

Input: issue, full trajectory (capped to the last ~12k tokens), patch and report.
Also runs an ablation `tier2nt` (same judge, no trajectory) to measure what the
trajectory adds.

Usage: python tier2_judge.py [--ablation]
"""
from __future__ import annotations

import argparse

from common import fill, load_prompt, truncate_middle
from monitor_utils import run_monitor

T = load_prompt("tier2_judge")
T_NT = load_prompt("tier2_notraj")
TRAJ_CHARS = 48_000  # ~12k tokens


def render_traj(traj, max_chars=TRAJ_CHARS) -> str:
    # skip the first user turn (it repeats the issue and the instructions)
    turns = traj[1:] if traj and traj[0]["role"] == "user" else traj
    parts = [f"[{'AGENT' if t['role'] == 'assistant' else 'ENVIRONMENT'}]\n{t['content']}" for t in turns]
    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = "...[earlier steps truncated]...\n" + text[-max_chars:]
    return text


def build(rec):
    return fill(T, issue=truncate_middle(rec["issue"], 8000), trajectory=render_traj(rec["trajectory"]),
                patch=truncate_middle(rec["patch"], 30000), report=rec["final_report"])


def build_nt(rec):
    return fill(T_NT, issue=truncate_middle(rec["issue"], 8000), patch=truncate_middle(rec["patch"], 30000),
                report=rec["final_report"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ablation", action="store_true", help="run the no-trajectory ablation instead")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    if a.ablation:
        run_monitor("tier2nt", "tier2", build_nt, workers=a.workers, max_tokens=12000)
    else:
        run_monitor("tier2", "tier2", build, workers=a.workers, max_tokens=12000)
