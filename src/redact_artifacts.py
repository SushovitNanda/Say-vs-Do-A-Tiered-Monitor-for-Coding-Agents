"""Redact credential-looking strings from committed artifacts, in place.

The hardcoded-secret attacks (A1) plant fake API keys; monitors quote them in their reasons, and
GitHub push protection rejects pushes that contain them. The writers in this repo now redact on
write, so this is only needed for artifacts produced before that change.

usage: python redact_artifacts.py [repo_root] [--dry-run]
Scores are untouched: only reason/finding text, patches in the fine-tuning data and the
hand-check/error-case sheets change (e.g. 'sk_live_51Hx...' -> 'sk_live_[REDACTED]').
"""
from __future__ import annotations

import sys
from pathlib import Path

from common import ROOT, count_secrets, redact_secrets

GLOBS = ["data/scores/*.jsonl", "data/ft/*.jsonl", "data/sample/*.jsonl", "results/*.md", "results/*.csv"]


def main(root: Path, dry: bool) -> None:
    total = 0
    for pat in GLOBS:
        for p in sorted(root.glob(pat)):
            text = p.read_bytes().decode("utf-8")  # bytes round-trip keeps the original line endings
            n = count_secrets(text)
            if not n:
                continue
            total += n
            print(f"{p.relative_to(root).as_posix()}: {n}")
            if not dry:
                p.write_bytes(redact_secrets(text).encode("utf-8"))
    print(("would redact" if dry else "redacted"), total, "strings under", root)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    main(Path(args[0]) if args else ROOT, "--dry-run" in sys.argv)
