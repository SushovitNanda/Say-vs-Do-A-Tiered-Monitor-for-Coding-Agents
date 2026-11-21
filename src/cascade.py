"""Cascade escalation logic and threshold selection.

    score0 = tier0(x)                              # free
    if score0 >= T0_flag:            FLAG
    elif score0 >= T0_esc or tier1(x) >= T1_esc:   # tier1 only runs if score0 < T0_esc
        FLAG if tier2(x) >= T2_flag else PASS
    else:                            PASS

Thresholds are chosen on the TRAIN split only: maximise recall subject to
FPR <= target and Tier 2 escalation rate <= budget. All scores are on [0, 1].
"""
from __future__ import annotations

import itertools
from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

INF = 9.0


@dataclass
class Thresholds:
    t0_flag: float
    t0_esc: float
    t1_esc: float
    t2_flag: float
    budget: float
    fpr_target: float


def apply(df: pd.DataFrame, th: Thresholds) -> pd.DataFrame:
    s0, s1, s2 = df["s0"].values, df["s1"].values, df["s2"].values
    direct = s0 >= th.t0_flag
    run_t1 = ~direct & (s0 < th.t0_esc)
    esc = ~direct & ((s0 >= th.t0_esc) | (run_t1 & (s1 >= th.t1_esc)))
    flag = direct | (esc & (s2 >= th.t2_flag))
    cost = run_t1 * df["c1"].values + esc * df["c2"].values
    lat = df["l0"].values + run_t1 * df["l1"].values + esc * df["l2"].values
    # continuous score for ROC: direct flags on top, escalated by tier-2 score, others at the bottom
    score = np.where(direct, 2.0 + s0, np.where(esc, 1.0 + s2, s1 * 0.5 * run_t1 + s0 * 0.5 * ~run_t1))
    return pd.DataFrame({"flag": flag, "escalated": esc, "ran_t1": run_t1, "cost": cost, "latency": lat,
                         "score": score}, index=df.index)


def _grid(x: np.ndarray, n: int = 40) -> np.ndarray:
    q = np.unique(np.quantile(x, np.linspace(0, 1, n)))
    return np.concatenate([q, [INF]])


def choose(train: pd.DataFrame, fpr_target: float = 0.05, budget: float = 0.3) -> Thresholds:
    y = train["label"].values.astype(bool)
    neg = (~y).sum()
    best, best_key = None, None
    for t0f in _grid(train["s0"].values, 12):
        for t0e in _grid(train["s0"].values, 12):
            if t0e > t0f:
                continue
            for t1e in _grid(train["s1"].values, 30):
                th = Thresholds(t0f, t0e, t1e, INF, budget, fpr_target)
                out = apply(train, th)
                if out["escalated"].mean() > budget + 1e-9:
                    continue
                for t2f in _grid(train["s2"].values, 30):
                    th.t2_flag = t2f
                    o = apply(train, th)
                    fp = (o["flag"].values & ~y).sum()
                    if fp / neg > fpr_target + 1e-9:
                        continue
                    rec = (o["flag"].values & y).sum() / y.sum()
                    key = (rec, -o["cost"].mean())
                    if best_key is None or key > best_key:
                        best_key, best = key, Thresholds(**asdict(th))
    return best


def apply_ens(df: pd.DataFrame, th: Thresholds) -> pd.DataFrame:
    """Variant: escalate on the T0+T1 mean score; flag directly if that mean is very high.
    Reuses Thresholds: t0_flag = direct-flag threshold on the mean, t1_esc = escalation threshold on the mean."""
    e = (df["s0"].values + df["s1"].values) / 2
    s2 = df["s2"].values
    direct = e >= th.t0_flag
    esc = ~direct & (e >= th.t1_esc)
    flag = direct | (esc & (s2 >= th.t2_flag))
    cost = df["c1"].values + esc * df["c2"].values
    lat = np.maximum(df["l0"].values, df["l1"].values) + esc * df["l2"].values
    score = np.where(direct, 2.0 + e, np.where(esc, 1.0 + s2, e))
    return pd.DataFrame({"flag": flag, "escalated": esc, "ran_t1": np.ones(len(df), bool), "cost": cost,
                         "latency": lat, "score": score}, index=df.index)


def choose_ens(train: pd.DataFrame, fpr_target: float = 0.05, budget: float = 0.3) -> Thresholds:
    y = train["label"].values.astype(bool)
    neg = (~y).sum()
    e = (train["s0"].values + train["s1"].values) / 2
    best, best_key = None, None
    for tf in _grid(e, 30):
        for te in _grid(e, 40):
            if te > tf:
                continue
            th = Thresholds(tf, INF, te, INF, budget, fpr_target)
            if apply_ens(train, th)["escalated"].mean() > budget + 1e-9:
                continue
            for t2f in _grid(train["s2"].values, 30):
                th.t2_flag = t2f
                o = apply_ens(train, th)
                if (o["flag"].values & ~y).sum() / neg > fpr_target + 1e-9:
                    continue
                key = ((o["flag"].values & y).sum() / y.sum(), -o["cost"].mean())
                if best_key is None or key > best_key:
                    best_key, best = key, Thresholds(**asdict(th))
    return best


def single_threshold(train_scores: np.ndarray, train_y: np.ndarray, fpr_target: float) -> float:
    """Smallest threshold whose train FPR <= target."""
    neg = np.sort(train_scores[train_y == 0])[::-1]
    k = int(np.floor(fpr_target * len(neg)))
    # flag if score > neg[k] (strictly above the k-th highest negative)
    return float(np.nextafter(neg[k], np.inf)) if k < len(neg) else float(neg.min())


def ensemble_score(df: pd.DataFrame, cols=("s0", "s1")) -> np.ndarray:
    return df[list(cols)].mean(axis=1).values


if __name__ == "__main__":
    print("see backtest.py")
