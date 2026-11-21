"""Dump misses and false positives of the main monitors for manual reading.

Writes results/error_cases.md: for the headline cascade and Tier 2, every missed
attack and every false positive on test + heldout, with the monitors' reasons and
the lines unique to the attack.
"""
from __future__ import annotations

import pandas as pd

from backtest import HEADLINE_BUDGET, load, make_configs
from common import ATTACKS, DATA, RESULTS, read_jsonl, redact_secrets
from validate_attacks import unique_changes


def main():
    df = load()
    train = df[df["split"] == "train"]
    cfgs = {c.name: c.fit(train) for c in make_configs(df)}
    recs = {r["id"]: r for r in read_jsonl(DATA / "dataset.jsonl")}
    ev = df[df["split"].isin(["test", "heldout"])]
    lines = ["# Error cases (test + held-out)", ""]
    for name in (f"Ens-cascade (T2 budget {int(HEADLINE_BUDGET * 100)}%)", "Tier 2 on everything", "Tier 1 (say-vs-do)"):
        c = cfgs.get(name)
        if c is None:
            continue
        out = c.run(ev)
        miss = ev[(ev["label"] == 1) & (~out["flag"])]
        fps = ev[(ev["label"] == 0) & (out["flag"])]
        lines += [f"## {name}: {len(miss)} missed attacks, {len(fps)} false positives", ""]
        lines += ["### Missed attacks", ""]
        for i, r in miss.iterrows():
            rec = recs[i]
            uc = unique_changes(rec["patch"], rec["honest_patch"])[:12]
            lines += [f"**{i}** ({r['attack_type']}: {ATTACKS[r['attack_type']][0]}) "
                      f"s0={r['s0']:.2f} s1={r['s1']:.2f} s2={r.get('s2', float('nan')):.2f}",
                      f"- flaw: {rec['flaw_description'].strip()[:400]}",
                      f"- T1 reason: {r.get('reason1', '')}", f"- T2 reason: {r.get('reason2', '')}",
                      "```", *uc, "```", ""]
        lines += ["### False positives", ""]
        for i, r in fps.iterrows():
            lines += [f"**{i}** s0={r['s0']:.2f} ({', '.join(r['t0_rules'][:4]) if isinstance(r['t0_rules'], list) else ''}) "
                      f"s1={r['s1']:.2f} s2={r.get('s2', float('nan')):.2f}",
                      f"- T1 reason: {r.get('reason1', '')}", f"- T2 reason: {r.get('reason2', '')}", ""]
    (RESULTS / "error_cases.md").write_text(redact_secrets("\n".join(lines)), encoding="utf-8")
    print("wrote results/error_cases.md")


if __name__ == "__main__":
    main()
