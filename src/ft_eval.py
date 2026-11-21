"""Stretch: score test + held-out examples with the fine-tuned small model on a local GPU.

score = P(SUSPICIOUS) / (P(SUSPICIOUS) + P(BENIGN)) at the answer position.
Also scores the un-tuned base model zero-shot as a reference (`--base-only`).

Usage:
  python ft_eval.py --adapter ../../models/ft_core --name ft_core
  python ft_eval.py --base-only --name base_qwen
Writes data/scores/<name>.jsonl (same schema as the LLM monitors: <name>_score in 0-100).
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch

from common import DATA, ROOT, read_jsonl, write_jsonl
from ft_prepare import ft_prompt

BASE = ROOT.parent / "models" / "Qwen3.5-4B"


def load_model(adapter: str | None):
    from transformers import AutoTokenizer
    # use the adapter's own tokenizer / chat template when present (it is what training used)
    tok = AutoTokenizer.from_pretrained(adapter if adapter and Path(adapter, "tokenizer.json").exists() else BASE)
    model = None
    if adapter:
        # AutoScientist adapters are keyed on the vision-language layout (model.language_model.layers.*),
        # so the base must be loaded as Qwen3_5ForConditionalGeneration for the LoRA keys to match.
        from transformers import AutoModelForImageTextToText
        model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16, device_map="cuda")
    else:
        try:
            from transformers import AutoModelForCausalLM
            model = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, device_map="cuda")
        except Exception as e:  # noqa: BLE001  (VLM checkpoints)
            print("CausalLM load failed, trying ImageTextToText:", repr(e)[:200])
            from transformers import AutoModelForImageTextToText
            model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16, device_map="cuda")
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter)
        # sanity check: the LoRA weights must actually be attached (module-name mismatches fail silently)
        n_lora = sum(1 for n, _ in model.named_parameters() if "lora_B" in n)
        nz = sum(int(p.abs().sum().item() > 0) for n, p in model.named_parameters() if "lora_B" in n)
        print(f"LoRA modules attached: {n_lora} (non-zero lora_B: {nz})", flush=True)
        if n_lora == 0 or nz == 0:
            raise RuntimeError("adapter weights not attached; check target module names")
    model.eval()
    return tok, model


def first_token(tok, word):
    return tok.encode(word, add_special_tokens=False)[0]


@torch.no_grad()
def score(tok, model, rec, ids_pos, ids_neg):
    msgs = [{"role": "user", "content": ft_prompt(rec)}]
    try:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    enc = tok(text, return_tensors="pt").to("cuda")
    logits = model(**enc).logits[0, -1].float()
    lp = torch.log_softmax(logits, -1)
    p_pos = lp[ids_pos].exp().sum().item()
    p_neg = lp[ids_neg].exp().sum().item()
    return p_pos / max(p_pos + p_neg, 1e-12), p_pos + p_neg, enc["input_ids"].shape[1]


def main(adapter, name, splits):
    tok, model = load_model(adapter)
    ids_pos = sorted({first_token(tok, w) for w in ("SUSPICIOUS", " SUSPICIOUS", "Susp", "SUS")})
    ids_neg = sorted({first_token(tok, w) for w in ("BENIGN", " BENIGN", "Ben", "BEN")})
    recs = [r for r in read_jsonl(DATA / "dataset.jsonl") if r["split"] in splits]
    out = []
    for i, r in enumerate(recs):
        t0 = time.time()
        s, mass, n_tok = score(tok, model, r, ids_pos, ids_neg)
        torch.cuda.synchronize()
        out.append({"id": r["id"], f"{name}_score": 100 * s, f"{name}_cost": 0.0,
                    f"{name}_latency": time.time() - t0, f"{name}_reason": f"label-mass={mass:.3f}",
                    f"{name}_prompt_tokens": n_tok})
        if i % 25 == 0:
            print(i, len(recs), f"{s:.3f} mass={mass:.3f} tok={n_tok} {time.time() - t0:.2f}s", flush=True)
    write_jsonl(DATA / "scores" / f"{name}.jsonl", out, redact=True)
    print("wrote", name, len(out))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--base-only", action="store_true")
    ap.add_argument("--name", required=True)
    ap.add_argument("--splits", default="train,test,heldout")
    a = ap.parse_args()
    main(None if a.base_only else a.adapter, a.name, a.splits.split(","))
