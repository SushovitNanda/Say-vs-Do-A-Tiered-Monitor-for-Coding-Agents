"""Stretch: expand the TRAINING data with fresh honest/attack pairs.

Uses llama-70b issues that are not in the main dataset at all (so nothing
overlaps the test or held-out splits), runs the same report -> attack ->
validation pipeline, and writes data/ft/extra_train.jsonl.
"""
from __future__ import annotations

import argparse
import glob
import random

import pyarrow.parquet as pq

from common import ATTACKS, DATA, pmap, read_jsonl, write_jsonl
from load_data import RAW, changed_lines, extract_issue, keep, normalise_traj, patch_files
from make_attacks import make_attack, make_report
from validate_attacks import keyword_leak, model_check, structural


def main(n: int, seed: int, workers: int):
    rng = random.Random(seed)
    used = {r["instance_id"] for r in read_jsonl(RAW / "sampled.jsonl")}
    cands = []
    for f in sorted(glob.glob(str(RAW / "train-*.parquet"))):
        t = pq.read_table(f, columns=["instance_id", "model_name", "exit_status", "target", "generated_patch"]).to_pylist()
        for i, r in enumerate(t):
            if r["model_name"] == "swe-agent-llama-70b" and r["instance_id"] not in used and keep(r):
                cands.append((f, i, r["instance_id"]))
    rng.shuffle(cands)
    seen, pick = set(), []
    for f, i, inst in cands:
        if inst not in seen:
            seen.add(inst)
            pick.append((f, i))
        if len(pick) >= n:
            break
    recs = []
    for f in {p[0] for p in pick}:
        tbl = pq.read_table(f)
        for ff, i in pick:
            if ff != f:
                continue
            r = tbl.slice(i, 1).to_pylist()[0]
            first_user = next((t["text"] for t in r["trajectory"] if t["role"] == "user"), "")
            recs.append({"id": f"{r['instance_id']}__{r['model_name']}__ft", "instance_id": r["instance_id"],
                         "source_model": r["model_name"], "issue": extract_issue(first_user),
                         "patch": r["generated_patch"].strip() + "\n", "patch_files": patch_files(r["generated_patch"]),
                         "changed_lines": changed_lines(r["generated_patch"])})
    print(f"{len(recs)} fresh records")
    reps = pmap(make_report, recs, workers=workers, desc="ft-reports")
    for r, rep in zip(recs, reps):
        r["final_report"] = rep
    recs = [r for r in recs if r.get("final_report")]
    rng.shuffle(recs)
    half = len(recs) // 2
    codes = list(ATTACKS)
    items = [(r, codes[i % 7]) for i, r in enumerate(recs[:half])]
    outs = pmap(make_attack, items, workers=workers, desc="ft-attacks")
    atks = []
    for (r, code), o in zip(items, outs):
        if o and o.get("attack_patch"):
            atks.append({**r, "id": r["id"] + "__atk", "honest_patch": r["patch"], "patch": o["attack_patch"],
                         "flaw_description": o["flaw_description"], "label": 1, "attack_type": code})
    atks = [a for a in atks if structural(a)[0]]
    checks = pmap(model_check, atks, workers=workers, desc="ft-validate")
    valid = [a for a, c in zip(atks, checks) if c and c["flaw_present"] and c["fix_preserved"]
             and not c["report_mentions_flaw"] and not keyword_leak(a)]
    honest = [{**r, "label": 0, "attack_type": None} for r in recs[half:]]
    write_jsonl(DATA / "ft" / "extra_train.jsonl", honest + valid, redact=True)
    print(f"extra train rows: {len(honest)} honest + {len(valid)} attacks")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    main(a.n, a.seed, a.workers)
