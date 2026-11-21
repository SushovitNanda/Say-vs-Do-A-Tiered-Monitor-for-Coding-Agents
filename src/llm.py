"""Provider abstraction for LLM calls.

complete(role_or_model, messages) -> text

* Adaption (OpenAI-compatible) first, OpenRouter fallback when a key exists.
* Retries with exponential backoff.
* On-disk cache (one JSON file per request hash) so reruns are free.
* Every call is logged to logs/llm_calls.jsonl with provider, model, tokens,
  latency and cost.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

CONFIG = yaml.safe_load((ROOT / "configs" / "models.yaml").read_text())
CACHE_DIR = ROOT / "cache" / "llm"
LOG_PATH = ROOT / "logs" / "llm_calls.jsonl"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

_log_lock = threading.Lock()
_clients: dict[str, OpenAI] = {}


class RateLimiter:
    """Simple sliding-window limiter: at most `rpm` request starts per 60 s (per process).
    The Adaption key is limited to roughly 50 requests/min across all models."""

    def __init__(self, rpm: float):
        self.rpm = rpm
        self.lock = threading.Lock()
        self.starts: list[float] = []

    def wait(self):
        while True:
            with self.lock:
                now = time.time()
                self.starts = [t for t in self.starts if now - t < 60]
                if len(self.starts) < self.rpm:
                    self.starts.append(now)
                    return
                sleep = 60 - (now - self.starts[0]) + 0.05
            time.sleep(max(sleep, 0.05))


LIMITER = RateLimiter(float(os.environ.get("LLM_RPM", "45")))


@dataclass
class LLMResult:
    text: str
    model: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    cost: float
    latency: float
    cached: bool
    reasoning: str = ""


def _client(provider: str) -> OpenAI | None:
    if provider in _clients:
        return _clients[provider]
    p = CONFIG["providers"][provider]
    key = os.environ.get(p["api_key_env"])
    if not key:
        return None
    c = OpenAI(base_url=p["base_url"], api_key=key, timeout=600, max_retries=0)
    _clients[provider] = c
    return c


def resolve(role_or_model: str) -> tuple[str, str]:
    """Return (provider, model) for a role name or a raw model id."""
    roles = CONFIG["roles"]
    if role_or_model in roles:
        r = roles[role_or_model]
        return r["provider"], r["model"]
    return "adaption", role_or_model


def price(model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0) -> float:
    p = CONFIG["prices"].get(model)
    if not p:
        return 0.0
    uncached = max(prompt_tokens - cached_tokens, 0)
    return (uncached * p["input"] + cached_tokens * p["cached"] + completion_tokens * p["output"]) / 1e6


def _key(provider, model, messages, kwargs) -> str:
    blob = json.dumps({"p": provider, "m": model, "msgs": messages, "kw": kwargs}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _log(rec: dict) -> None:
    with _log_lock:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")


def complete_full(role_or_model: str, messages: list[dict], *, tag: str = "", use_cache: bool = True,
                  retries: int = 6, **kwargs) -> LLMResult:
    provider, model = resolve(role_or_model)
    kwargs.setdefault("temperature", 0.0)
    key = _key(provider, model, messages, kwargs)
    cpath = CACHE_DIR / f"{key}.json"
    if use_cache and cpath.exists():
        d = json.loads(cpath.read_text(encoding="utf-8"))
        res = LLMResult(**{**d, "cached": True})
        _log({"ts": time.time(), "tag": tag, "provider": res.provider, "model": res.model, "cached": True,
              "prompt_tokens": res.prompt_tokens, "completion_tokens": res.completion_tokens,
              "cost": res.cost, "latency": res.latency})
        return res

    providers = [provider] + [p for p in ("openrouter",) if p != provider and _client(p)]
    last_err = None
    for prov in providers:
        client = _client(prov)
        if client is None:
            continue
        attempt = 0
        n429 = 0
        while attempt < retries:
            LIMITER.wait()
            t0 = time.time()
            try:
                resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
                dt = time.time() - t0
                msg = resp.choices[0].message
                text = msg.content or ""
                reasoning = getattr(msg, "reasoning_content", None) or ""
                if not reasoning and hasattr(msg, "model_extra") and msg.model_extra:
                    reasoning = msg.model_extra.get("reasoning_content") or msg.model_extra.get("reasoning") or ""
                u = resp.usage
                pt = getattr(u, "prompt_tokens", 0) or 0
                ct = getattr(u, "completion_tokens", 0) or 0
                cached_t = 0
                try:
                    cached_t = (u.prompt_tokens_details.cached_tokens or 0) if u.prompt_tokens_details else 0
                except Exception:
                    pass
                cost = price(model, pt, ct, cached_t)
                res = LLMResult(text=text, model=model, provider=prov, prompt_tokens=pt, completion_tokens=ct,
                                cost=cost, latency=dt, cached=False, reasoning=reasoning[:20000])
                if text.strip():
                    cpath.write_text(json.dumps(res.__dict__), encoding="utf-8")
                _log({"ts": time.time(), "tag": tag, "provider": prov, "model": model, "cached": False,
                      "prompt_tokens": pt, "completion_tokens": ct, "cached_tokens": cached_t,
                      "cost": cost, "latency": dt, "finish": resp.choices[0].finish_reason})
                if not text.strip() and attempt < retries - 1:
                    last_err = RuntimeError("empty response")
                    attempt += 1
                    time.sleep(2 * attempt)
                    continue
                return res
            except Exception as e:  # noqa: BLE001
                last_err = e
                status = getattr(e, "status_code", None)
                _log({"ts": time.time(), "tag": tag, "provider": prov, "model": model, "error": repr(e)[:300],
                      "status": status, "latency": time.time() - t0})
                if status in (400, 401, 403, 404, 422):
                    break
                if status == 429 and n429 < 60:  # rate limit: wait and retry without using up an attempt
                    n429 += 1
                    time.sleep(5 + random.random() * 15)
                    continue
                attempt += 1
                time.sleep(min(60, 2 ** attempt + 1))
    raise RuntimeError(f"LLM call failed for {model}: {last_err!r}")


def complete(role_or_model: str, messages: list[dict], **kwargs) -> str:
    return complete_full(role_or_model, messages, **kwargs).text


def extract_json(text: str):
    """Pull the last JSON object out of a model reply."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.S)
    cands = m[::-1] if m else []
    # fallback: outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        cands.append(text[start:end + 1])
    for c in cands:
        try:
            return json.loads(c)
        except Exception:
            try:
                return json.loads(re.sub(r",\s*([}\]])", r"\1", c))
            except Exception:
                continue
    return None


def usage_summary() -> dict:
    tot = {}
    if not LOG_PATH.exists():
        return tot
    for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r.get("cached") or "error" in r:
            continue
        m = r["model"]
        t = tot.setdefault(m, {"calls": 0, "cost": 0.0, "prompt_tokens": 0, "completion_tokens": 0})
        t["calls"] += 1
        t["cost"] += r.get("cost", 0)
        t["prompt_tokens"] += r.get("prompt_tokens", 0)
        t["completion_tokens"] += r.get("completion_tokens", 0)
    return tot


if __name__ == "__main__":
    import sys
    roles = sys.argv[1:] or list(CONFIG["roles"].keys())
    for role in roles:
        r = complete_full(role, [{"role": "user", "content": "Reply with exactly: OK"}], tag="smoke",
                          use_cache=False, max_tokens=2000)
        print(f"{role:10s} {r.provider}/{r.model}: {r.text.strip()[:60]!r} "
              f"tok={r.prompt_tokens}/{r.completion_tokens} lat={r.latency:.1f}s cost={r.cost:.6f}")
