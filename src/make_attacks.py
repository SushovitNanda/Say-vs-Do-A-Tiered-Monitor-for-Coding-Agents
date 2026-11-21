"""Red team: generate final reports for every record and inject one flaw into half of them.

Design choice (avoids a stylistic tell): every final report, honest or attack, is
written by the same `reporter` model from the same prompt, always from the HONEST
patch. For attack records this gives exactly the threat model we want: the report
describes the legitimate fix and is silent about the inserted flaw.
"""
from __future__ import annotations

import argparse
import random
from collections import Counter

from common import ATTACKS, DATA, fill, load_prompt, pmap, read_jsonl, tag, truncate_middle, write_jsonl
from llm import complete_full

REPORT_T = load_prompt("report")
ATTACK_T = load_prompt("attack")


def make_report(rec):
    r = complete_full("reporter", [{"role": "user", "content": fill(
        REPORT_T, issue=truncate_middle(rec["issue"], 6000), patch=rec["patch"])}],
        tag="report", max_tokens=4000)
    return r.text.strip()


def make_attack(item):
    rec, code = item
    name, desc = ATTACKS[code]
    prompt = fill(ATTACK_T, attack_code=code, attack_name=name, attack_description=desc,
                  issue=truncate_middle(rec["issue"], 6000), patch=rec["patch"])
    r = complete_full("attacker", [{"role": "user", "content": prompt}], tag=f"attack_{code}",
                      max_tokens=16000, temperature=0.7)
    patch = tag(r.text, "sabotaged_patch")
    flaw = tag(r.text, "flaw_description")
    if patch:
        patch = patch.strip().strip("`")
        if patch.startswith("diff") is False and "diff --git" in patch:
            patch = patch[patch.index("diff --git"):]
        patch = patch.rstrip() + "\n"
    return {"attack_patch": patch, "flaw_description": flaw, "attacker_cost": r.cost}


def main(n_attack: int, seed: int, workers: int):
    rng = random.Random(seed)
    recs = read_jsonl(DATA / "raw" / "sampled.jsonl")
    print(f"{len(recs)} sampled records")

    reports = pmap(make_report, recs, workers=workers, desc="reports")
    for rec, rep in zip(recs, reports):
        rec["final_report"] = rep

    # choose attack records stratified by source model, balanced attack types
    by_model = {}
    for r in recs:
        by_model.setdefault(r["source_model"], []).append(r)
    attack_ids = set()
    frac = n_attack / len(recs)
    for m, rows in by_model.items():
        rng.shuffle(rows)
        k = round(len(rows) * frac)
        attack_ids.update(r["id"] for r in rows[:k])
    attack_recs = [r for r in recs if r["id"] in attack_ids]
    rng.shuffle(attack_recs)
    codes = list(ATTACKS)
    items = [(r, codes[i % len(codes)]) for i, r in enumerate(attack_recs)]
    print("attack types:", Counter(c for _, c in items), "by model:", Counter(r["source_model"] for r, _ in items))

    outs = pmap(make_attack, items, workers=workers, desc="attacks")

    honest, attacks = [], []
    for r in recs:
        if r["id"] not in attack_ids:
            honest.append({**r, "label": 0, "attack_type": None})
    for (r, code), o in zip(items, outs):
        attacks.append({**r, "id": r["id"] + "__atk", "honest_patch": r["patch"],
                        "patch": (o or {}).get("attack_patch"), "label": 1, "attack_type": code,
                        "flaw_description": (o or {}).get("flaw_description")})
    write_jsonl(DATA / "raw" / "honest.jsonl", honest)
    write_jsonl(DATA / "attacks" / "attacks_raw.jsonl", attacks)
    print(f"honest={len(honest)} attacks={len(attacks)} "
          f"(missing patch: {sum(1 for a in attacks if not a['patch'])})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n_attack", type=int, default=224)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=24)
    a = ap.parse_args()
    main(a.n_attack, a.seed, a.workers)
