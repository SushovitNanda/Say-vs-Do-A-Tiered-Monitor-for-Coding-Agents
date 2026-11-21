"""Shared runner for LLM monitors (Tier 1, Tier 2 and ablations)."""
from __future__ import annotations

import re

from common import DATA, pmap, read_jsonl, write_jsonl
from llm import complete_full, extract_json


def parse_suspicion(text: str):
    j = extract_json(text)
    if isinstance(j, dict) and "suspicion" in j:
        try:
            return max(0.0, min(100.0, float(j["suspicion"]))), j
        except (TypeError, ValueError):
            pass
    m = re.search(r'"?suspicion"?\s*[:=]\s*(\d+(?:\.\d+)?)', text)
    if m:
        return max(0.0, min(100.0, float(m.group(1)))), j
    return None, j


def run_monitor(name: str, role: str, build_prompt, recs=None, workers: int = 32, max_tokens: int = 8000,
                out_name: str | None = None, **kw):
    recs = recs if recs is not None else read_jsonl(DATA / "dataset.jsonl")

    def one(rec):
        msgs = [{"role": "user", "content": build_prompt(rec)}]
        r = complete_full(role, msgs, tag=name, max_tokens=max_tokens, **kw)
        s, j = parse_suspicion(r.text)
        cost, lat = r.cost, r.latency
        if s is None:  # one retry with a different sampling seed
            r2 = complete_full(role, msgs + [{"role": "assistant", "content": r.text},
                                             {"role": "user", "content": "Reply with only the JSON object."}],
                               tag=name + "_retry", max_tokens=max_tokens, **kw)
            s, j = parse_suspicion(r2.text)
            cost += r2.cost
            lat += r2.latency
        return {"id": rec["id"], f"{name}_score": s, f"{name}_reason": (j or {}).get("reason", "") if isinstance(j, dict) else "",
                f"{name}_cost": cost, f"{name}_latency": lat, f"{name}_model": r.model,
                f"{name}_prompt_tokens": r.prompt_tokens, f"{name}_completion_tokens": r.completion_tokens,
                f"{name}_raw": None if s is not None else r.text[-2000:]}

    res = pmap(one, recs, workers=workers, desc=name)
    res = [x for x in res if x]
    write_jsonl(DATA / "scores" / f"{out_name or name}.jsonl", res, redact=True)
    ok = [x for x in res if x[f"{name}_score"] is not None]
    print(f"{name}: {len(ok)}/{len(recs)} scored; total cost {sum(x[f'{name}_cost'] for x in res):.3f}")
    return res
