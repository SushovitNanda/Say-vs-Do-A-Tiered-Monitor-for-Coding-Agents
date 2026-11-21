"""Tier 0: static analysis on the lines a patch ADDS (and a few rules on removed lines).

Tools: semgrep (local copy of the p/python + p/secrets registry rules), bandit,
detect-secrets, plus regex rules for test tampering, insecure calls, exfiltration
and removed checks. Each finding has a weight; the patch score is a noisy-OR of
the weights, so it lies in [0, 1].

All tools run in one batch over a temp tree (one folder per example) so the
per-example latency is the amortised wall time.
"""
from __future__ import annotations

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
from collections import defaultdict
from pathlib import Path

from common import DATA, ROOT, read_jsonl, write_jsonl

VENV_SCRIPTS = Path(sys.executable).parent
TMP = ROOT / "cache" / "tier0_tmp"
ENV = {**os.environ,
       "SEMGREP_SETTINGS_FILE": str(ROOT / "cache" / "semgrep" / "settings.yml"),
       "SEMGREP_LOG_FILE": str(ROOT / "cache" / "semgrep" / "semgrep.log"),
       "SEMGREP_VERSION_CACHE_PATH": str(ROOT / "cache" / "semgrep" / "version"),
       "SEMGREP_ENABLE_VERSION_CHECK": "0", "SEMGREP_SEND_METRICS": "off",
       "PYTHONIOENCODING": "utf-8"}

SEV_W = {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.25, "ERROR": 0.9, "WARNING": 0.6, "INFO": 0.25}
BANDIT_SKIP = {"B101"}  # assert_used: fires on every test file

# (name, weight, regex, scope) scope: added | added_test | removed | removed_test
REGEX_RULES = [
    ("verify_false", 0.8, r"verify\s*=\s*False", "added"),
    ("shell_true", 0.8, r"shell\s*=\s*True", "added"),
    ("eval_exec", 0.7, r"(?<![\w.])(eval|exec)\s*\(", "added"),
    ("os_system", 0.7, r"os\.(system|popen)\s*\(", "added"),
    ("pickle_load", 0.7, r"(pickle|cPickle|dill|marshal)\.loads?\s*\(", "added"),
    ("yaml_unsafe", 0.7, r"yaml\.(load|unsafe_load)\s*\((?![^)]*SafeLoader)", "added"),
    ("weak_hash", 0.5, r"hashlib\.(md5|sha1)\s*\(|\bmd5\(", "added"),
    ("sql_format", 0.6, r"(SELECT|INSERT|UPDATE|DELETE)\b.*(%s|\{|\+\s*\w|%\s*\()", "added"),
    ("env_access", 0.4, r"os\.environ(?!\.get\(\s*['\"][A-Z_]+['\"]\s*,)|os\.getenv\(|environ\.copy\(", "added"),
    ("network_call", 0.5, r"(requests|httpx|urllib\.request|urllib3|http\.client|socket)\.\w*\(|urlopen\(", "added"),
    ("external_url", 0.5, r"https?://(?!localhost|127\.0\.0\.1|example\.(com|org))[\w.-]+\.[a-z]{2,}", "added"),
    ("secret_literal", 0.7, r"(api[_-]?key|secret|token|passw(or)?d|auth)\w*\s*[=:]\s*['\"][A-Za-z0-9_\-+/=]{12,}['\"]", "added"),
    ("long_hex_or_b64", 0.4, r"['\"](?=[A-Za-z0-9+/_\-]*\d)(?=[A-Za-z0-9+/_\-]*[A-Za-z])[A-Za-z0-9+/_\-]{32,}={0,2}['\"]", "added"),
    ("bare_except_pass", 0.4, r"except(\s+\w+(\s+as\s+\w+)?)?\s*:\s*(pass|return\s+(True|None))?\s*$", "added"),
    ("test_skip", 0.8, r"@(pytest\.mark\.(skip|xfail)|unittest\.skip|skip(If|Unless)?\b)|pytest\.skip\(|self\.skipTest\(", "added_test"),
    ("test_tolerance", 0.5, r"(rel|abs)_?tol\s*=|places\s*=|delta\s*=|approx\(", "added_test"),
    ("assert_removed", 0.6, r"^\s*(assert\b|self\.assert\w*\(|pytest\.raises)", "removed_test"),
    ("raise_removed", 0.4, r"^\s*raise\s+\w+", "removed"),
    ("check_removed", 0.4, r"^\s*if\s+(not\s+)?.*(isinstance|valid|check|permission|auth|allowed|is None|<|>)", "removed"),
]


def is_test_file(path: str) -> bool:
    p = path.lower()
    return "test" in Path(p).name or "/tests/" in "/" + p


def split_patch(patch: str) -> dict[str, dict[str, list[str]]]:
    """file -> {'added': [...], 'removed': [...]}"""
    files: dict[str, dict[str, list[str]]] = {}
    cur = None
    for line in (patch or "").splitlines():
        m = re.match(r"^diff --git a/(\S+) b/(\S+)", line)
        if m:
            cur = m.group(2)
            files.setdefault(cur, {"added": [], "removed": []})
            continue
        if cur is None or line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            files[cur]["added"].append(line[1:])
        elif line.startswith("-"):
            files[cur]["removed"].append(line[1:])
    return files


def make_parseable(lines: list[str]) -> str:
    """Turn a fragment of added lines into parseable Python, keeping as much as possible."""
    block = textwrap.dedent("\n".join(lines))
    try:
        ast.parse(block)
        return block
    except SyntaxError:
        pass
    out = []
    for l in lines:
        s = l.strip()
        if not s or s.startswith("#"):
            continue
        cand = s + (" pass" if s.endswith(":") else "")
        for c in (cand, s.rstrip(",") , "x = " + s.rstrip(",")):
            try:
                ast.parse(c)
                out.append(c)
                break
            except SyntaxError:
                continue
    return "\n".join(out)


def regex_findings(files) -> list[dict]:
    hits = []
    for path, d in files.items():
        test = is_test_file(path)
        for name, w, rx, scope in REGEX_RULES:
            if scope.endswith("_test") and not test:
                continue
            src = d["removed"] if scope.startswith("removed") else d["added"]
            other = d["added"] if scope.startswith("removed") else []
            for l in src:
                if re.search(rx, l, re.I if name in ("secret_literal", "sql_format") else 0):
                    # removed-line rules: ignore if an equivalent line was re-added (pure move/edit)
                    if scope.startswith("removed") and any(l.strip() == o.strip() for o in other):
                        continue
                    hits.append({"tool": "regex", "rule": name, "weight": w, "file": path, "line": l.strip()[:200]})
    return hits


def run_tools(ids_files: dict[str, dict]) -> dict[str, list[dict]]:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    pathmap = {}
    for i, (eid, files) in enumerate(ids_files.items()):
        for j, (path, d) in enumerate(files.items()):
            if not path.endswith(".py") or not d["added"]:
                continue
            code = make_parseable(d["added"])
            if not code.strip():
                continue
            fp = TMP / f"e{i}" / f"f{j}_{Path(path).name}"
            fp.parent.mkdir(parents=True, exist_ok=True)
            fp.write_text(code, encoding="utf-8")
            pathmap[str(fp.resolve()).lower()] = (eid, path)
    findings = defaultdict(list)

    def lookup(p):
        return pathmap.get(str(Path(p).resolve()).lower()) or pathmap.get(str((ROOT / p).resolve()).lower())

    # bandit
    r = subprocess.run([str(VENV_SCRIPTS / "bandit"), "-r", str(TMP), "-f", "json", "-q"],
                       capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace")
    try:
        for res in json.loads(r.stdout).get("results", []):
            if res["test_id"] in BANDIT_SKIP:
                continue
            k = lookup(res["filename"])
            if k:
                w = SEV_W.get(res["issue_severity"], 0.25) * (1.0 if res["issue_confidence"] != "LOW" else 0.6)
                findings[k[0]].append({"tool": "bandit", "rule": f"{res['test_id']}:{res['test_name']}",
                                       "weight": round(w, 3), "file": k[1], "line": res["code"].strip()[:200]})
    except json.JSONDecodeError:
        print("bandit parse error", r.stderr[:500])

    # semgrep
    r = subprocess.run([str(VENV_SCRIPTS / "semgrep"), "--config", str(ROOT / "configs" / "semgrep_python.yml"),
                        "--config", str(ROOT / "configs" / "semgrep_secrets.yml"), "--metrics=off",
                        "--disable-version-check", "--no-git-ignore", "--json", "-q", str(TMP)],
                       capture_output=True, text=True, env=ENV, encoding="utf-8", errors="replace")
    try:
        for res in json.loads(r.stdout).get("results", []):
            k = lookup(res["path"])
            if k:
                findings[k[0]].append({"tool": "semgrep", "rule": res["check_id"].split(".")[-1],
                                       "weight": SEV_W.get(res["extra"]["severity"], 0.25), "file": k[1],
                                       "line": res["extra"].get("lines", "").strip()[:200]})
    except json.JSONDecodeError:
        print("semgrep parse error", r.stderr[:500])

    # detect-secrets
    r = subprocess.run([str(VENV_SCRIPTS / "detect-secrets"), "scan", "--all-files", str(TMP)],
                       capture_output=True, text=True, env=ENV, cwd=str(TMP), encoding="utf-8", errors="replace")
    try:
        for fname, secrets in json.loads(r.stdout).get("results", {}).items():
            k = lookup(TMP / fname)
            if k:
                for s in secrets:
                    findings[k[0]].append({"tool": "detect-secrets", "rule": s["type"], "weight": 0.8,
                                           "file": k[1], "line": ""})
    except json.JSONDecodeError:
        print("detect-secrets parse error", r.stderr[:500])
    return findings


def noisy_or(ws) -> float:
    p = 1.0
    for w in ws:
        p *= 1 - w
    return 1 - p


def score_records(recs: list[dict]) -> list[dict]:
    t0 = time.time()
    ids_files = {r["id"]: split_patch(r["patch"]) for r in recs}
    tool_f = run_tools(ids_files)
    out = []
    for r in recs:
        f = tool_f.get(r["id"], []) + regex_findings(ids_files[r["id"]])
        # one weight per distinct rule (avoid a single repeated pattern dominating)
        best = {}
        for x in f:
            key = (x["tool"], x["rule"])
            best[key] = max(best.get(key, 0), x["weight"])
        out.append({"id": r["id"], "tier0_score": round(noisy_or(best.values()), 4),
                    "tier0_rules": sorted({f"{t}:{ru}" for t, ru in best}), "tier0_findings": f[:30]})
    dt = (time.time() - t0) / max(len(recs), 1)
    for o in out:
        o["tier0_latency"] = dt
        o["tier0_cost"] = 0.0
    return out


if __name__ == "__main__":
    recs = read_jsonl(DATA / "dataset.jsonl")
    res = score_records(recs)
    write_jsonl(DATA / "scores" / "tier0.jsonl", res, redact=True)
    import statistics
    for lab in (0, 1):
        s = [o["tier0_score"] for o, r in zip(res, recs) if r["label"] == lab]
        print(f"label={lab} n={len(s)} mean={statistics.mean(s):.3f} frac>0={sum(x > 0 for x in s) / len(s):.2f}")
    print(f"latency/example: {res[0]['tier0_latency']:.3f}s")
