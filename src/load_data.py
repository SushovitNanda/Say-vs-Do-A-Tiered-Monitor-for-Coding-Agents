"""Sample and normalise honest SWE-agent trajectories.

Reads the parquet shards of nebius/SWE-agent-trajectories from data/raw/,
keeps resolved, submitted, Python-only patches with 5-150 changed lines,
takes at most one run per GitHub issue (so no issue leaks across splits),
and writes data/raw/sampled.jsonl.
"""
from __future__ import annotations

import argparse
import glob
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

MAX_OBS_CHARS = 3000


def changed_lines(patch: str) -> int:
    return sum(1 for l in patch.splitlines()
               if (l.startswith("+") or l.startswith("-")) and not l.startswith(("+++", "---")))


def patch_files(patch: str) -> list[str]:
    return re.findall(r"^diff --git a/(\S+)", patch, re.M)


def keep(r: dict) -> bool:
    p = r["generated_patch"] or ""
    if not (r["target"] and r["exit_status"] == "submitted" and p.strip()):
        return False
    files = patch_files(p)
    if not files or not all(f.endswith(".py") for f in files):
        return False
    return 5 <= changed_lines(p) <= 150


def extract_issue(first_user: str) -> str:
    m = re.search(r"ISSUE:\n(.*?)\n\s*INSTRUCTIONS:", first_user, re.S)
    return (m.group(1) if m else first_user[:6000]).strip()


def normalise_traj(traj: list[dict]) -> list[dict]:
    out = []
    for t in traj:
        if t["role"] == "system":
            continue
        txt = t.get("text") or ""
        if txt == "None":
            continue
        role = "assistant" if t["role"] == "ai" else "user"
        if role == "user" and len(txt) > MAX_OBS_CHARS:
            txt = txt[:MAX_OBS_CHARS // 2] + "\n...[output truncated]...\n" + txt[-MAX_OBS_CHARS // 2:]
        out.append({"role": role, "content": txt})
    return out


def main(n_total: int, seed: int):
    rng = random.Random(seed)
    cols = ["instance_id", "model_name", "exit_status", "target", "generated_patch"]
    cands = defaultdict(list)  # model -> list of (shard, row_idx, instance)
    for f in sorted(glob.glob(str(RAW / "train-*.parquet"))):
        t = pq.read_table(f, columns=cols).to_pylist()
        for i, r in enumerate(t):
            if keep(r):
                cands[r["model_name"]].append((f, i, r["instance_id"]))
    print("candidates:", {m: len(v) for m, v in cands.items()})

    # one run per instance overall; give scarce models first pick of instances
    used = set()
    chosen = defaultdict(list)
    models = sorted(cands, key=lambda m: len({c[2] for c in cands[m]}))
    per_model_cap = {m: n_total for m in models}
    # cap scarce models so the big model still has room; aim for >=3 models
    for m in models[:-1]:
        per_model_cap[m] = min(len({c[2] for c in cands[m]}), n_total // 4)
    for m in models:
        rows = cands[m][:]
        rng.shuffle(rows)
        for f, i, inst in rows:
            if inst in used or len(chosen[m]) >= per_model_cap[m]:
                continue
            used.add(inst)
            chosen[m].append((f, i))
    remaining = n_total - sum(len(chosen[m]) for m in models[:-1])
    chosen[models[-1]] = chosen[models[-1]][:remaining]
    print("chosen:", {m: len(v) for m, v in chosen.items()})

    by_file = defaultdict(list)
    for m, lst in chosen.items():
        for f, i in lst:
            by_file[f].append(i)

    out = []
    for f, idxs in by_file.items():
        tbl = pq.read_table(f)
        for i in idxs:
            r = tbl.slice(i, 1).to_pylist()[0]
            traj = r["trajectory"]
            first_user = next((t["text"] for t in traj if t["role"] == "user"), "")
            run_idx = Counter()
            rec = {
                "id": f"{r['instance_id']}__{r['model_name']}",
                "instance_id": r["instance_id"],
                "repo": r["instance_id"].rsplit("-", 1)[0],
                "source_model": r["model_name"],
                "issue": extract_issue(first_user),
                "trajectory": normalise_traj(traj),
                "patch": r["generated_patch"].strip() + "\n",
                "patch_files": patch_files(r["generated_patch"]),
                "changed_lines": changed_lines(r["generated_patch"]),
            }
            out.append(rec)
    rng.shuffle(out)
    path = RAW / "sampled.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in out:
            fh.write(json.dumps(rec) + "\n")
    print(f"wrote {len(out)} records to {path}")
    print(Counter(r["source_model"] for r in out))
    # tiny committed sample (no trajectories) for reviewers
    sample_dir = ROOT / "data" / "sample"
    sample_dir.mkdir(parents=True, exist_ok=True)
    with open(sample_dir / "honest_sample.jsonl", "w", encoding="utf-8") as fh:
        for rec in out[:5]:
            fh.write(json.dumps({k: v for k, v in rec.items() if k != "trajectory"}) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=420)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    main(a.n, a.seed)
