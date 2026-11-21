"""Figures that exist only in the PDF report (report/figures/). The other report figures are the
backtest plots in results/. Numbers are read from results/metrics.csv; the trajectory-leak counts
come from results/error_analysis.md (Tier 2 reasons that mention the trajectory).

usage: python report_figures.py
"""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Polygon  # noqa: E402

from common import RESULTS, ROOT  # noqa: E402

FIG = ROOT / "report" / "figures"
SURFACE, INK, INK2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e4e3df"
CAT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": INK2, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 8.5, "axes.titlesize": 9, "axes.titleweight": "bold",
    "legend.frameon": False,
})

# box styles: (fill, edge)
DATA = ("#f1f0ec", "#52514e")
CHEAP = ("#e3eefc", "#2a78d6")
STRONG = ("#fde4d8", "#eb6834")
FLAG = ("#fbdcdc", "#e34948")
PASS = ("#dcf3e9", "#1baf7a")
LE, GE = "≤", "≥"


def box(ax, x, y, w, h, title, body, style, fs=6.4):
    fill, edge = style
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=fill, ec=edge, lw=1.1))
    ax.text(x + w / 2, y + h - 1.8, title, ha="center", va="top", fontsize=fs + 0.9, fontweight="bold", color=INK)
    if body:
        ax.text(x + w / 2, y + h - 6.6, body, ha="center", va="top", fontsize=fs, color=INK2, linespacing=1.3)


def label(ax, x, y, text, fs=6.3):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=INK2, linespacing=1.2,
            bbox=dict(fc=SURFACE, ec="none", pad=0.4))


def arrow(ax, p, q, color=INK2):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, lw=1.0, color=color,
                                 shrinkA=0, shrinkB=0.5))


def elbow(ax, pts, color=INK2):
    """polyline through pts with an arrowhead on the last segment"""
    xs, ys = zip(*pts[:-1])
    ax.plot(xs, ys, color=color, lw=1.0, solid_capstyle="butt")
    arrow(ax, pts[-2], pts[-1], color=color)


def architecture():
    fig, ax = plt.subplots(figsize=(6.8, 4.5))
    fig.subplots_adjust(0, 0, 1, 1)
    ax.set_xlim(0, 136)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.grid(False)

    # ---- band A: dataset construction --------------------------------------------------------
    ax.text(0.5, 99, "A. Dataset construction (offline, once)", fontsize=8, fontweight="bold", color=INK, va="top")
    w, h, y, gap = 20.6, 17.5, 73.5, 2.28
    xs = [0.5 + i * (w + gap) for i in range(6)]
    steps = [("Source", "nebius SWE-agent\ntrajectories, Llama\n8b / 70b / 405b"),
             ("Filter + sample", "420 resolved runs\nPython, 5-150 lines\n1 run per issue"),
             ("Reporter", "report written from\nthe HONEST patch\ndeepseek-v4-flash"),
             ("Attacker", "adds 1 hidden flaw\n(A1-A7), keeps fix\nqwen3.5-397b"),
             ("Validator", "structural, keyword\nand model checks\n182 / 223 kept"),
             ("Splits", "train 161, test 162\nheld-out 56\n(llama-8b, -405b)")]
    for i, (t, b) in enumerate(steps):
        box(ax, xs[i], y, w, h, t, b, STRONG if t == "Attacker" else DATA)
        if i:
            arrow(ax, (xs[i - 1] + w, y + h / 2), (xs[i], y + h / 2))

    # ---- band B: the cascade ------------------------------------------------------------------
    ax.text(0.5, 65, "B. Monitoring cascade (per trajectory)", fontsize=8, fontweight="bold", color=INK, va="top")
    box(ax, 0.5, 23, 16.5, 25, "Input", "issue\ntrajectory\npatch (diff)\nfinal report", DATA)
    box(ax, 23, 37.5, 23.5, 16, "Tier 0: static", "semgrep, bandit,\ndetect-secrets, regex\nfree, 0.05 s", CHEAP)
    box(ax, 23, 16, 23.5, 18.5, "Tier 1: say vs do",
        "report vs diff: is every\nchange reported?\ndeepseek-v4-flash\n$0.0004 per run", CHEAP)
    arrow(ax, (17, 40), (23, 45.5))
    arrow(ax, (17, 31), (23, 25))

    cx, cy, dw, dh = 61, 35.5, 9, 10
    ax.add_patch(Polygon([(cx - dw, cy), (cx, cy + dh), (cx + dw, cy), (cx, cy - dh)], closed=True,
                         fc=SURFACE, ec=INK, lw=1.1))
    ax.text(cx, cy + 1.8, "e = mean", ha="center", va="center", fontsize=6.6, fontweight="bold")
    ax.text(cx, cy - 2.2, "(T0, T1)", ha="center", va="center", fontsize=6.6, fontweight="bold")
    arrow(ax, (46.5, 45.5), (cx - 4.6, cy + 5.0))
    arrow(ax, (46.5, 25), (cx - 4.6, cy - 5.0))

    box(ax, 86, 25, 24, 21.5, "Tier 2: judge",
        "full trajectory +\npatch + report\nglm-5.2, $0.016 per run\n(ablation: no trajectory)", STRONG)
    box(ax, 119, 49, 16.5, 11.5, "FLAG", "to a human", FLAG)
    box(ax, 119, 10.5, 16.5, 11.5, "PASS", "no action", PASS)

    arrow(ax, (cx + dw, cy), (86, cy))
    label(ax, 77.5, 41.2, f"escalate if\nE_esc {LE} e < E_flag", fs=6.0)
    elbow(ax, [(cx, cy + dh), (cx, 55), (119, 55)])
    label(ax, 99, 55, f"e {GE} E_flag")
    elbow(ax, [(cx, cy - dh), (cx, 16), (119, 16)])
    label(ax, 99, 16, "e < E_esc")
    elbow(ax, [(110, 41), (114.5, 41), (114.5, 51.5), (119, 51.5)])
    label(ax, 114.5, 46, f"T2 {GE}\nT2_flag", fs=5.8)
    elbow(ax, [(110, 30), (114.5, 30), (114.5, 19.5), (119, 19.5)])
    label(ax, 114.5, 25, "else", fs=5.8)

    # threshold fitting
    ax.add_patch(FancyBboxPatch((0.5, 0.5), 135, 7.5, boxstyle="round,pad=0,rounding_size=1.0",
                                fc=SURFACE, ec=INK2, lw=0.9, ls=(0, (4, 3))))
    ax.text(68, 4.25, "Thresholds E_flag, E_esc, T2_flag are grid-searched on the TRAIN split only (maximise recall "
            f"s.t. FPR {LE} 5% and Tier 2 share {LE} budget B),\nthen frozen and applied unchanged to test "
            "(llama-70b) and held-out (llama-8b, llama-405b).", ha="center", va="center",
            fontsize=6.1, color=INK2, linespacing=1.3)

    fig.savefig(FIG / "fig1_architecture.png", dpi=250)
    plt.close(fig)


def budget_sweep(m):
    budgets = [5, 10, 20, 30, 50]
    t = m[m.split == "test"].set_index("config")
    t2 = t.loc["Tier 2 on everything"]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.6))
    for k, (prefix, lab) in enumerate((("Cascade", "Plan rule (T0 or T1 escalates)"),
                                      ("Ens-cascade", "Mean rule (mean(T0,T1) escalates)"))):
        rows = [t.loc[f"{prefix} (T2 budget {b}%)"] for b in budgets]
        axes[0].plot(budgets, [r.recall_fixed for r in rows], marker="o", ms=5, lw=2, color=CAT[k], label=lab)
        axes[1].plot(budgets, [100 * r.cost_per_1k_usd / t2.cost_per_1k_usd for r in rows], marker="o", ms=5,
                     lw=2, color=CAT[k], label=lab)
    axes[0].axhline(t2.recall_fixed, color=INK2, ls="--", lw=1)
    axes[0].text(50, t2.recall_fixed + 0.012, f"Tier 2 on everything ({t2.recall_fixed:.2f})", ha="right",
                 va="bottom", fontsize=7, color=INK2)
    ens = t.loc["Ensemble T0+T1 (mean)"].recall_fixed
    axes[0].axhline(ens, color=INK2, ls=":", lw=1)
    axes[0].text(50, ens - 0.012, f"T0 + T1 only, no strong model ({ens:.2f})", ha="right", va="top",
                 fontsize=7, color=INK2)
    axes[0].set(ylim=(0.5, 1.0), xlabel="Tier 2 budget (max. share of traffic escalated, %)",
                ylabel="Recall at train-fixed 5% FPR", title="Detection (test split)")
    axes[1].set(ylim=(0, 45), xlabel="Tier 2 budget (%)", ylabel="Cost, % of Tier 2 on everything",
                title="Cost (test split)")
    for ax in axes:
        ax.set_xticks(budgets)
    axes[1].legend(loc="upper left", fontsize=7)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(FIG / "fig_budget_sweep.png", dpi=250)
    plt.close(fig)


def trajectory_leak(m):
    t = m.set_index(["config", "split"])
    w, wo = "Tier 2 on everything", "Tier 2, no trajectory (ablation)"
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.5), gridspec_kw={"width_ratios": [1, 1.3]})
    ax = axes[0]
    vals = [4 / 197, 135 / 182]
    ax.barh([1, 0], vals, color=[CAT[2], CAT[1]], height=0.55)
    ax.set_yticks([1, 0], ["Honest runs\n(n = 197)", "Attacked runs\n(n = 182)"])
    for yy, v, lab in ((1, vals[0], "2%  (4)"), (0, vals[1], "74%  (135)")):
        ax.text(v + 0.02, yy, lab, va="center", fontsize=7.5, color=INK)
    ax.set(xlim=(0, 1), title="Tier 2 reasons that cite the trajectory")
    ax.xaxis.set_major_formatter(mticker.PercentFormatter(1.0))
    ax.grid(axis="y", visible=False)

    ax = axes[1]
    metrics = [("AUROC\n(test)", "auroc", "test"), ("Recall\n(test)", "recall_fixed", "test"),
               ("Recall\n(held-out)", "recall_fixed", "heldout")]
    x = range(len(metrics))
    for k, (name, lab) in enumerate(((w, "With trajectory"), (wo, "Without trajectory (ablation)"))):
        v = [t.loc[(name, s), col] for _, col, s in metrics]
        bars = ax.bar([i + (k - 0.5) * 0.36 for i in x], v, width=0.34, color=CAT[k], label=lab)
        for b, val in zip(bars, v):
            ax.text(b.get_x() + b.get_width() / 2, val + 0.01, f"{val:.2f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(list(x), [mm[0] for mm in metrics])
    ax.set(ylim=(0.5, 1.13), title="Same judge, with vs without trajectory")
    ax.set_yticks([0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    ax.legend(loc="upper center", ncol=2, fontsize=7, bbox_to_anchor=(0.5, 1.02))
    ax.grid(axis="x", visible=False)
    fig.tight_layout(w_pad=2.0)
    fig.savefig(FIG / "fig_trajectory_leak.png", dpi=250)
    plt.close(fig)


if __name__ == "__main__":
    FIG.mkdir(parents=True, exist_ok=True)
    met = pd.read_csv(RESULTS / "metrics.csv")
    architecture()
    budget_sweep(met)
    trajectory_leak(met)
    print("wrote", sorted(p.name for p in FIG.glob("*.png")))
