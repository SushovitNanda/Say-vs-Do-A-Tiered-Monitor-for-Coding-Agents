"""Merge honest records and validated attacks into data/dataset.jsonl with splits.

Splits
* heldout : every trajectory from the held-out generating models (test only).
* train / test : the remaining model, split 50/50 stratified by (label, attack_type).
Thresholds are fixed on `train` only.
"""
from __future__ import annotations

import random
from collections import Counter, defaultdict

from common import DATA, read_jsonl, write_jsonl

HELDOUT_MODELS = {"swe-agent-llama-8b", "swe-agent-llama-405b"}
SEED = 0


def main():
    honest = read_jsonl(DATA / "raw" / "honest.jsonl")
    attacks = read_jsonl(DATA / "attacks" / "attacks_valid.jsonl")
    rows = honest + attacks
    rng = random.Random(SEED)
    strata = defaultdict(list)
    for r in rows:
        if r["source_model"] in HELDOUT_MODELS:
            r["split"] = "heldout"
        else:
            strata[(r["label"], r["attack_type"])].append(r)
    for key, lst in strata.items():
        rng.shuffle(lst)
        half = len(lst) // 2 + (len(lst) % 2 and rng.random() < 0.5)
        for i, r in enumerate(lst):
            r["split"] = "train" if i < half else "test"
    rng.shuffle(rows)
    write_jsonl(DATA / "dataset.jsonl", rows)
    c = Counter((r["split"], r["label"]) for r in rows)
    print("rows:", len(rows), dict(sorted(c.items())))
    print("attack types:", dict(sorted(Counter(r["attack_type"] for r in rows if r["label"]).items())))
    # small committed sample without full trajectories
    sample = [{k: v for k, v in r.items() if k != "trajectory"} for r in rows[:10]]
    write_jsonl(DATA / "sample" / "dataset_sample.jsonl", sample, redact=True)


if __name__ == "__main__":
    main()
