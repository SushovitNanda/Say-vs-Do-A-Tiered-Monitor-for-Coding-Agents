"""Build the PDF report: report/Say_vs_Do_report.pdf.

Main-results, cost and per-attack-type tables are generated from results/*.csv, so the report
tracks the backtest. Prose numbers match README.md. Figures: report/figures/ (report_figures.py)
and results/*.png (backtest.py).

usage: python report_figures.py && python make_report.py
needs: pip install -r requirements-report.txt
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, ListFlowable, ListItem, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from common import RESULTS, ROOT

OUT = ROOT / "report" / "Say_vs_Do_report.pdf"
FIGS = ROOT / "report" / "figures"
TITLE = "Say vs Do: A Tiered Monitor for Coding Agents"
REPO = "github.com/SushovitNanda/Say-vs-Do-A-Tiered-Monitor-for-Coding-Agents"

# ---- fonts: STIX (serif) and DejaVu (sans, mono) ship with matplotlib, so the build is portable ----
TTF = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
for name, f in {"Serif": "STIXGeneral.ttf", "Serif-B": "STIXGeneralBol.ttf", "Serif-I": "STIXGeneralItalic.ttf",
                "Serif-BI": "STIXGeneralBolIta.ttf", "Sans": "DejaVuSans.ttf", "Sans-B": "DejaVuSans-Bold.ttf",
                "Sans-I": "DejaVuSans-Oblique.ttf", "Sans-BI": "DejaVuSans-BoldOblique.ttf",
                "Mono": "DejaVuSansMono.ttf"}.items():
    pdfmetrics.registerFont(TTFont(name, str(TTF / f)))
pdfmetrics.registerFontFamily("Serif", normal="Serif", bold="Serif-B", italic="Serif-I", boldItalic="Serif-BI")
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-B", italic="Sans-I", boldItalic="Sans-BI")

INK, INK2, RULE, HEAD = colors.HexColor("#0b0b0b"), colors.HexColor("#52514e"), colors.HexColor("#b9b8b3"), \
    colors.HexColor("#f1f0ec")
ACCENT = colors.HexColor("#2a78d6")

BODY = ParagraphStyle("body", fontName="Serif", fontSize=10.3, leading=13.2, alignment=TA_JUSTIFY,
                      spaceAfter=4.5, textColor=INK)
S = {
    "title": ParagraphStyle("title", fontName="Sans-B", fontSize=17, leading=21, alignment=TA_CENTER,
                            spaceAfter=6, textColor=INK),
    "author": ParagraphStyle("author", fontName="Serif", fontSize=10.5, leading=13, alignment=TA_CENTER,
                             textColor=INK2, spaceAfter=2),
    "abs_h": ParagraphStyle("abs_h", fontName="Sans-B", fontSize=9.5, leading=12, alignment=TA_CENTER,
                            spaceBefore=8, spaceAfter=3),
    "abs": ParagraphStyle("abs", parent=BODY, fontSize=9.6, leading=12.4, leftIndent=0.9 * cm,
                          rightIndent=0.9 * cm),
    "h1": ParagraphStyle("h1", fontName="Sans-B", fontSize=12, leading=15, spaceBefore=9, spaceAfter=4,
                         textColor=INK),
    "h2": ParagraphStyle("h2", fontName="Sans-B", fontSize=10, leading=13, spaceBefore=6, spaceAfter=2.5,
                         textColor=INK),
    "body": BODY,
    "cap": ParagraphStyle("cap", fontName="Serif", fontSize=8.9, leading=11, alignment=TA_JUSTIFY,
                          textColor=INK2, spaceBefore=2, spaceAfter=7),
    "cell": ParagraphStyle("cell", fontName="Sans", fontSize=7.4, leading=9.0, textColor=INK),
    "cellb": ParagraphStyle("cellb", fontName="Sans-B", fontSize=7.4, leading=9.0, textColor=INK),
    "rq": ParagraphStyle("rq", parent=BODY, leftIndent=0.5 * cm, spaceAfter=3.5),
    "ref": ParagraphStyle("ref", fontName="Serif", fontSize=8.8, leading=11, leftIndent=0.55 * cm,
                          firstLineIndent=-0.55 * cm, spaceAfter=2.5, textColor=INK),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.6, leading=9.6, leftIndent=0.5 * cm,
                           textColor=INK, spaceBefore=2, spaceAfter=5),
}
W = A4[0] - 2 * 2.0 * cm  # text width


def P(text, style="body"):
    return Paragraph(text, S[style])


def H1(t):
    return P(t, "h1")


def H2(t):
    return P(t, "h2")


def code(t):
    return f'<font name="Mono" size="8.6">{t}</font>'


def bullets(items, style="body"):
    return ListFlowable([ListItem(P(i, style), leftIndent=12) for i in items], bulletType="bullet",
                        start="•", leftIndent=12, bulletFontName="Serif", bulletFontSize=9, spaceAfter=3)


def figure(path, caption, width=1.0):
    from reportlab.lib.utils import ImageReader
    iw, ih = ImageReader(str(path)).getSize()
    w = W * width
    return KeepTogether([Image(str(path), width=w, height=w * ih / iw), P(caption, "cap")])


def table(rows, col_w, caption, bold_rows=(), align_right_from=1, caption_above=True):
    data = [[Paragraph(str(c), S["cellb" if (r == 0 or r in bold_rows) else "cell"]) for c in row]
            for r, row in enumerate(rows)]
    t = Table(data, colWidths=[W * f for f in col_w], repeatRows=1, hAlign="CENTER")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEAD),
        ("LINEABOVE", (0, 0), (-1, 0), 0.9, INK),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, INK),
        ("LINEBELOW", (0, -1), (-1, -1), 0.9, INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        *[("BACKGROUND", (0, r), (-1, r), colors.HexColor("#eef4fc")) for r in bold_rows],
    ]))
    cap = P(caption, "cap")
    return KeepTogether([cap, t, Spacer(1, 6)] if caption_above else [t, cap])


# ---- data ----------------------------------------------------------------------------------------
M = pd.read_csv(RESULTS / "metrics.csv").set_index(["config", "split"])
RBT = pd.read_csv(RESULTS / "recall_by_attack_type.csv", index_col=0)


def m(cfg, split, col):
    return M.loc[(cfg, split), col]


def f2(x):
    """round half up from the 4-decimal CSV value (0.975 -> 0.98), matching the README"""
    from decimal import ROUND_HALF_UP, Decimal
    return str(Decimal(f"{x:.4f}").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def main_table():
    rows = [["Monitor", "AUROC test [95% CI]", "AUROC held-out", "Recall @ fixed thr. test / held-out",
             "FPR test", "$ / 1k traj. (test)", "Tier 2 share"]]
    cfgs = [("Tier 0 (static)", "Tier 0: static analysis"),
            ("Tier 1 (say-vs-do)", "Tier 1: say vs do"),
            ("Ensemble T0+T1 (mean)", "T0 + T1 mean (no strong model)"),
            ("Tier 2 on everything", "Tier 2 judge on everything"),
            ("Cascade (T2 budget 30%)", "Cascade, plan rule, B = 30%"),
            ("Ens-cascade (T2 budget 20%)", "Cascade, mean rule, B = 20%"),
            ("Ens-cascade (T2 budget 30%)", "Cascade, mean rule, B = 30%"),
            ("Tier 2, no trajectory (ablation)", "Tier 2 without trajectory (ablation)"),
            ("Ens-cascade, no-traj T2 (T2 budget 20%)", "Mean-rule cascade, no-traj. Tier 2, B = 20%")]
    for c, name in cfgs:
        t2 = m(c, "test", "t2_rate")
        share = "100%" if c.startswith("Tier 2") else ("–" if pd.isna(t2) else f"{100 * t2:.0f}%")
        rows.append([name, f"{f2(m(c, 'test', 'auroc'))} [{f2(m(c, 'test', 'auroc_lo'))}, {f2(m(c, 'test', 'auroc_hi'))}]",
                     f2(m(c, "heldout", "auroc")),
                     f"{f2(m(c, 'test', 'recall_fixed'))} / {f2(m(c, 'heldout', 'recall_fixed'))}",
                     f2(m(c, "test", "fpr_fixed")), f2(m(c, 'test', 'cost_per_1k_usd')), share])
    return rows


def type_table():
    names = [("Tier 0 (static)", "Tier 0"), ("Tier 1 (say-vs-do)", "Tier 1"), ("Ensemble T0+T1 (mean)", "T0 + T1 mean"),
             ("Tier 2 on everything", "Tier 2 on everything"), ("Ens-cascade (T2 budget 30%)", "Cascade, mean, 30%"),
             ("Tier 2, no trajectory (ablation)", "Tier 2, no trajectory")]
    rows = [["Monitor", "A1 cred.", "A2 inject.", "A3 insecure", "A4 tests", "A5 scope", "A6 check", "A7 exfil."]]
    for c, n in names:
        rows.append([n] + [f"{100 * RBT.loc[c, a]:.0f}" for a in ["A1", "A2", "A3", "A4", "A5", "A6", "A7"]])
    return rows


def cost_table():
    rows = [["Monitor", "$ / 1k traj.", "Mean latency", "P95 latency", "Note"]]
    for c, n, note in [("Tier 0 (static)", "Tier 0: static", "local tools"),
                       ("Tier 1 (say-vs-do)", "Tier 1: deepseek-v4-flash", "reasoning model, ~2k thinking tokens"),
                       ("Tier 1 alt: gemma-4-31b-it", "Tier 1 alt.: gemma-4-31b-it", "non-reasoning; AUROC 0.92"),
                       ("Tier 2 on everything", "Tier 2: glm-5.2", "full trajectory"),
                       ("Ens-cascade (T2 budget 30%)", "Cascade, mean rule, B = 30%",
                        "T0 and T1 in parallel, then Tier 2 if escalated")]:
        lat = [m(c, "test", k) for k in ("latency_mean_s", "latency_p95_s")]
        rows.append([n, f2(m(c, 'test', 'cost_per_1k_usd'))] +
                    [f"{v:.2f} s" if v < 1 else f"{v:.1f} s" for v in lat] + [note])
    return rows


# ---- page furniture ---------------------------------------------------------------------------------
def on_page(canv, doc):
    canv.saveState()
    canv.setFont("Sans", 7.5)
    canv.setFillColor(INK2)
    if doc.page > 1:
        canv.drawString(2.0 * cm, A4[1] - 1.25 * cm, TITLE)
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.4)
        canv.line(2.0 * cm, A4[1] - 1.4 * cm, A4[0] - 2.0 * cm, A4[1] - 1.4 * cm)
    canv.drawCentredString(A4[0] / 2, 1.1 * cm, str(doc.page))
    canv.restoreState()


# ---- content ----------------------------------------------------------------------------------------
def story():
    s = []
    s += [Spacer(1, 4), P(TITLE, "title"),
          P("Sushovit Nanda", "author"),
          P(f'November 2026 · Code, data and results: <font name="Mono" size="8.5">{REPO}</font>', "author"),
          P("Abstract", "abs_h"),
          P("Coding agents with write access to real repositories can slip a small harmful change into an otherwise "
            "correct patch and describe only the legitimate fix in their final report. Reading every trajectory with "
            "a frontier model is expensive, so we ask a control question: <i>how much of a strong judge's detection "
            "can a cheap monitoring hierarchy retain at a fixed false-positive budget?</i> We build a benchmark of "
            "<b>379 real SWE-agent trajectories</b> from three Llama-based agents, 182 of which carry one concealed "
            "flaw (seven attack types) inserted by a red-team model from a different family and validated by "
            "structural and model checks. We evaluate static analysis (Tier 0), a cheap <i>say vs do</i> check that "
            "compares the agent's report against its diff (Tier 1), a strong full-trajectory judge (Tier 2), and "
            "cascades that escalate only suspicious runs. With every threshold fixed on a training split at 5% FPR, "
            "a cascade that sends 27% of traffic to Tier 2 reaches <b>recall 0.87 vs 0.91</b> for the judge on "
            "every run (paired Δ = −0.04, 95% CI [−0.11, +0.03]) at <b>34% of the cost</b>, and matches "
            "the judge on two held-out agent models (0.96) at 14% of the cost. Reading the judge's rationales "
            "reveals that post-hoc attack injection leaks through the trajectory (cited in 74% of attack verdicts "
            "vs 2% of honest ones); without the trajectory the judge falls to AUROC 0.95, and we report a "
            "conservative cascade accordingly. A LoRA-tuned 4B open model improves on its zero-shot baseline "
            "(AUROC 0.83 → 0.88) at ~90× lower latency, but does not surpass the prompted cheap monitor.",
            "abs")]

    s += [H1("1 Introduction"),
          P("Coding agents now run with write access to real repositories. An agent that is misaligned, or simply "
            "prompt-injected, does not need to do anything dramatic to cause harm: one hardcoded token, one "
            f"{code('verify=False')}, one weakened test, hidden behind a confident “I fixed the bug” summary. "
            "The AI-control agenda [1] treats such agents as potentially adversarial and asks which monitoring and "
            "escalation protocols keep them safe without assuming they are aligned. A natural protocol is a "
            "<b>monitor hierarchy</b>: cheap checks on everything, and an expensive, more capable monitor only on "
            "what the cheap checks find suspicious. Whether such a hierarchy is worth deploying is an empirical "
            "question about detection, false positives, cost and latency, and it must be answered at a fixed, low "
            "false-positive rate, because human review is the scarce resource."),
          P("This report studies that question on coding agents. Its cheap tier borrows the idea behind "
            "<i>Say, Do, or Both?</i>, that an agent's claims can be checked against its actions: the Tier 1 monitor "
            "compares what the agent <i>says</i> it did (its final report) with what it <i>did</i> (its diff). "
            "<b>Threat model.</b> An agent asked to fix a GitHub issue fixes it <i>and</i> inserts one small harmful "
            "change, then writes a report that describes only the legitimate fix. The monitor sees what a "
            "deployment would see (issue, trajectory, patch and report) and must decide whether to send the run to "
            "a human. <b>Contributions:</b>"),
          bullets(["A benchmark of 379 real SWE-agent trajectories (182 with validated, concealed flaws across seven "
                   "attack types) with in-distribution and <b>held-out-agent</b> splits, built for about $15 of API spend.",
                   "A three-tier monitor and two escalation rules, backtested with thresholds fixed on train at 5% FPR, "
                   "with bootstrap CIs and paired tests against the strong judge on everything.",
                   "Evidence that a cascade keeps the judge's recall within CI at a third of its cost, and a "
                   "rationale analysis showing that the judge exploits an artefact of post-hoc attack injection, "
                   "with a conservative no-trajectory estimate.",
                   "A small fine-tuned open monitor (Qwen3.5-4B, LoRA) as a candidate replacement for the cheap tier."])]

    s += [H1("2 Research questions"),
          P("The questions are ordered so that each answer motivates the next (Figure 1 shows the full pipeline)."),
          P("<b>RQ1 – Cheap signals.</b> How well do cheap monitors (static analysis and a say-vs-do consistency "
            "check) detect concealed flaws at a strict false-positive rate, and which attack types does each cover?", "rq"),
          P("<b>RQ2 – Cascade.</b> Since RQ1 shows complementary but incomplete coverage, how much of the strong "
            "judge's recall can a cascade recover at a fixed 5% FPR as a function of the share of traffic sent to "
            "the judge (the <i>Tier 2 budget</i>), and at what cost?", "rq"),
          P("<b>RQ3 – Transfer.</b> Do thresholds fitted on one agent model (llama-70b) transfer to trajectories "
            "from agent models never used for tuning (llama-8b, llama-405b)?", "rq"),
          P("<b>RQ4 – What the judge relies on.</b> The cascade's ceiling is the judge (RQ2–RQ3). What evidence "
            "does the judge actually use, and how much of its advantage (and the cascade's) survives without the "
            "trajectory?", "rq"),
          P("<b>RQ5 – A cheaper cheap tier.</b> RQ2 makes Tier 1 the step every run passes through, and it is "
            "the slowest step in the cascade. Can a small fine-tuned open model replace it?", "rq"),
          figure(FIGS / "fig1_architecture.png",
                 "<b>Figure 1.</b> Overview. <b>(A)</b> Dataset construction: honest SWE-agent runs are filtered and "
                 "given a report written from the honest patch; for a disjoint subset an attacker model inserts one "
                 "concealed flaw, which a validator from another model family must confirm. <b>(B)</b> The monitoring "
                 "cascade (mean-escalation rule shown): Tier 0 and Tier 1 run on every trajectory, their mean score "
                 "either flags, passes, or escalates the run to the Tier 2 judge. All thresholds are fitted on the "
                 "train split and frozen.")]

    s += [H1("3 Experimental setup"),
          H2("3.1 Data"),
          P("Trajectories come from <font name='Mono' size='8.6'>nebius/SWE-agent-trajectories</font> [5]: about 80k "
            "SWE-agent [2] runs on real GitHub issues in the style of SWE-bench [3], produced by three agents "
            "(swe-agent-llama-8b, -70b, -405b). The honest pool keeps resolved runs (target = True, exit status "
            "<i>submitted</i>) whose patch touches only Python files and changes 5 to 150 lines, with <b>at most one "
            "run per issue</b> so that no issue appears twice; 420 runs were sampled. SWE-agent runs end with a "
            "<i>submit</i> action and no written summary, so every run receives a 2–5 sentence report from the "
            "same reporter model and prompt, written from the <b>honest</b> patch. This removes a stylistic tell "
            "between classes and is exactly the threat for attacked runs: the report describes the real fix and is "
            "silent about the flaw."),
          H2("3.2 Attacks and validation"),
          P("For a disjoint set of runs, the attacker (qwen3.5-397b) edits the patch to add exactly one flaw of a "
            "requested type while keeping the fix, aiming for 32 attacks per type (Table 1). An attack is kept only "
            "if (i) the patch is a well-formed diff that differs from the honest one (omissions count: a check the "
            "honest fix added and the attack drops); (ii) the lines unique to the attack contain no self-incriminating "
            "word; (iii) no identifier unique to the attack appears in the report; and (iv) a validator from a "
            "different family (deepseek-v4-flash), <i>given the attacker's own flaw description</i>, confirms that "
            "the flaw is present and of the requested type, that the fix is preserved, and that the report is "
            "silent about it. <b>182 of 223 attacks (82%) passed</b>; disabled-check attacks (A6) passed least "
            "often. A <b>human check of 20 random validated attacks found 19 valid</b> (95%; Wilson 95% CI "
            "76–99%). The invalid one adds a duplicate parameter to a function signature, a syntax error "
            "rather than a working flaw; no other attack in the dataset has this pattern."),
          table([["Code", "Attack type", "Example", "Valid"],
                 ["A1", "Hardcoded credential", "API key or token as a string literal", "30"],
                 ["A2", "Injection", "eval, os.system / shell=True, string-built SQL", "25"],
                 ["A3", "Insecure call", "verify=False, yaml.load, pickle.loads, md5", "24"],
                 ["A4", "Test tampering", "skip, delete or try/except an assertion", "28"],
                 ["A5", "Scope creep", "unrequested change to an unrelated constant or default", "31"],
                 ["A6", "Disabled check", "remove or weaken validation, auth or error handling", "15"],
                 ["A7", "Exfiltration hook", "send os.environ or key material over the network or to disk", "29"]],
                [0.07, 0.2, 0.6, 0.08],
                "<b>Table 1.</b> Attack taxonomy and number of attacks that passed validation (182 in total)."),
          H2("3.3 Splits"),
          P("Every run from llama-8b and llama-405b goes to a <b>held-out</b> set (56 runs, 26 attacks) that is never "
            "used for any choice. llama-70b runs are split 50/50, stratified by label and attack type, into "
            "<b>train</b> (161 runs, 78 attacks) and <b>test</b> (162 runs, 78 attacks). Train is used only to fit "
            "thresholds; all reported numbers are on test or held-out."),
          H2("3.4 Models and infrastructure"),
          P("All LLMs are served through an OpenAI-compatible API (Adaption). Roles: attacker qwen3.5-397b; Tier 2 "
            "judge glm-5.2 (a different family from the attacker, so it cannot simply recognise its own writing); "
            "Tier 1, validator and reporter deepseek-v4-flash; alternative Tier 1 gemma-4-31b-it. Every call is cached "
            "and logged with tokens, latency and cost (tokens × list price). The key was limited to about 40 "
            "requests per minute, so a client-side rate limiter paces all calls; latencies were measured under that "
            "load and should be read as relative. Local models run on a single RTX 4080 Laptop GPU (12 GB). Total "
            "API spend for the whole study was about <b>$15</b>.")]

    s += [H1("4 Methodology"),
          H2("4.1 Monitors"),
          P("Table 2 lists the monitors. Each LLM monitor returns JSON with a score and a short reason; the "
            "reasons are kept for error analysis (Section 6)."),
          table([["Tier", "Input", "Model", "Output"],
                 ["0: static", "lines added and removed by the patch", "none",
                  "semgrep (p/python, p/secrets), bandit, detect-secrets [6] and regex rules for test tampering, insecure "
                  "calls, exfiltration and removed checks; noisy-OR of per-rule weights in [0, 1]"],
                 ["1: say vs do", "issue + report + patch", "deepseek-v4-flash",
                  "lists every change in the patch, marks each as mentioned in the report / needed for the issue / "
                  "risky, then gives a suspicion score 0–100"],
                 ["2: judge", "issue + trajectory (last ~12k tokens) + patch + report", "glm-5.2",
                  "full sabotage review: suspicion score 0–100 and a one-line reason; run on every example "
                  "to give the upper bound"],
                 ["2: ablation", "issue + patch + report (no trajectory)", "glm-5.2", "as Tier 2"]],
                [0.1, 0.23, 0.15, 0.52], "<b>Table 2.</b> Monitors. Scores are rescaled to [0, 1]."),
          H2("4.2 Escalation rules"),
          P("Let s0, s1, s2 be the Tier 0, 1 and 2 scores. The <b>plan rule</b> flags if s0 ≥ T0_flag, "
            "escalates if s0 ≥ T0_esc, and otherwise runs Tier 1 and escalates if s1 ≥ T1_esc, passing "
            "the rest; an escalated run is flagged iff s2 ≥ T2_flag. The <b>mean rule</b>, a variant added "
            "because the two cheap scores are complementary, runs both cheap tiers and uses e = (s0 + s1)/2: flag "
            "if e ≥ E_flag, escalate if E_esc ≤ e &lt; E_flag, pass otherwise (Figure 1B). A cascade's "
            "continuous score, used for AUROC, is s2 on escalated runs and the cheap score otherwise, offset so "
            "that direct flags rank above escalated runs, which rank above passes."),
          H2("4.3 Threshold fitting"),
          P("For each rule and each <b>Tier 2 budget</b> B ∈ {5, 10, 20, 30, 50}% the thresholds are "
            "grid-searched on train to maximise recall subject to FPR ≤ 5% and an escalation rate ≤ B. "
            "Single monitors and ensembles get one threshold each, chosen on train for FPR ≤ 5%. Thresholds are "
            "then frozen and applied unchanged to test and held-out, so the reported FPR is what the threshold "
            "actually delivers out of sample. For the headline cascade (mean rule, B = 30%) the fitted values are "
            "E_flag = 0.67, E_esc = 0.34 and T2_flag = 0.70."),
          H2("4.4 Metrics and statistics"),
          P("We report AUROC; recall at the train-fixed threshold (the deployment-relevant number) with its realised "
            "FPR, precision and F1; recall at 1% and 5% FPR read off the test ROC; mean API cost per 1,000 "
            "trajectories from logged tokens; mean and P95 latency along each run's cascade path (Tier 0 and "
            "Tier 1 in parallel under the mean rule, in sequence under the plan rule); and the realised share of traffic sent to Tier 2. Uncertainty is a 95% percentile bootstrap "
            "(1,000 resamples). Each cascade is compared with Tier 2 on everything by a <b>paired bootstrap</b> "
            "over the same resampled examples, which is far tighter than comparing two marginal CIs."),
          H2("4.5 Fine-tuned monitor (RQ5)"),
          P("Training data are <b>247 fresh</b> honest and attack pairs (142 honest, 105 validated attacks) generated "
            "with the same pipeline from llama-70b issues that appear nowhere in the evaluation set, so train, test "
            "and held-out are untouched. Qwen3.5-4B is LoRA-tuned (r = 16, α = 32, all attention and MLP "
            "projections) [4] with Adaption AutoScientist. The service requires at least 1,000 rows, so we ran two "
            "variants: <b>A</b>, the real rows repeated 5×; and <b>B</b>, the real rows plus 800 rows of "
            "Adaption's synthetic domain augmentation. Scoring runs locally in bf16 as "
            "P(SUSPICIOUS) / (P(SUSPICIOUS) + P(BENIGN)) at the answer token (the two labels carry > 99% of the "
            "probability mass); the same prompt scores the un-tuned model as a zero-shot baseline, and thresholds "
            "are fitted on train like every other monitor's.")]

    s += [H1("5 Results"),
          P("Table 3 summarises every single monitor and the main cascades on both evaluation splits; the "
            "subsections below answer the research questions in order."),
          table(main_table(), [0.29, 0.16, 0.1, 0.16, 0.08, 0.11, 0.1],
                "<b>Table 3.</b> Main results. Test: n = 162 (78 attacks); held-out: n = 56 (26 attacks). "
                "“Recall @ fixed thr.” uses the threshold chosen on train for 5% FPR; “FPR test” is "
                "what that threshold gives on test. Cost is the mean API cost per 1,000 trajectories. "
                "Highlighted rows are the strong judge and the headline cascade.", bold_rows=(4, 7)),
          H2("RQ1: cheap monitors are complementary, and neither is enough at a strict FPR"),
          P("Static analysis is free and fast (0.05 s) and reaches AUROC 0.85 (Figure 2), recall 0.62 at the fixed threshold. "
            "The say-vs-do check ranks better (AUROC 0.92) but at a strict threshold it recalls only 0.58: it "
            "<i>notices</i> most unreported changes, and its reasons name the unreported edit in most scope-creep and "
            "disabled-check cases, but it rates “unreported but not obviously dangerous” changes around "
            "30–65 out of 100, below any threshold that keeps FPR at 5%. The two signals fail on different "
            "attacks (Table 4): Tier 0 covers the “loud” types (credentials, injection, insecure "
            "calls) and is blind to scope creep (12%) and disabled checks (0%); Tier 1 catches every credential and "
            "exfiltration attack but few test-tampering ones. Their mean reaches AUROC 0.94 and recall 0.73 at "
            "<b>2.5% of the judge's cost</b>, still significantly below the judge (paired Δ recall "
            "−0.18 [−0.29, −0.08]). <b>Answer:</b> cheap monitors cover the loud attacks for almost "
            "nothing but cannot turn subtle ones (A4–A6) into flags, which motivates escalation."),
          table(type_table(), [0.25, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
                "<b>Table 4.</b> Recall (%) by attack type at the train-fixed 5%-FPR threshold, test and held-out "
                "combined. A6 has only 15 attacks, so its CIs are wide. Every configuration, including the local "
                "models, is plotted in results/recall_by_attack_type.png.", bold_rows=(4, 5)),
          figure(RESULTS / "roc_curves.png",
                 "<b>Figure 2.</b> ROC curves on the in-distribution test split. The dotted line marks 5% FPR. "
                 "“Cascade” is the plan rule and “Ens-cascade” the mean rule, both at a 30% Tier 2 "
                 "budget.", width=0.5),
          H2("RQ2: a cascade keeps the judge's recall within CI at a third of its cost"),
          P("Figure 3 sweeps the Tier 2 budget. Recall rises with the budget and saturates around B = 30%, where "
            "the train-fitted thresholds stop using the extra allowance (the mean-rule cascade sends 27% of test "
            "traffic to Tier 2 at both B = 30% and 50%). The mean rule dominates the plan rule at small budgets "
            "(0.74 vs 0.59 recall at B = 5%), because averaging lets a moderately suspicious Tier 1 score and a "
            "moderately suspicious Tier 0 score jointly trigger escalation. At B = 30% the mean-rule cascade reaches "
            "<b>recall 0.87</b> at 4% FPR versus 0.91 for the judge on everything, a paired difference of "
            "<b>−0.04 [−0.11, +0.03]</b> that is not significant (Table 5), at <b>34% of the cost</b> ($5.44 vs $15.96 "
            "per 1,000 trajectories). At B = 20% it costs 20% of the judge but loses recall significantly "
            "(−0.09 [−0.18, −0.01]). Figure 4 places every configuration on the cost–recall plane. "
            "<b>Answer:</b> escalating roughly a quarter of the traffic recovers nearly all of the judge's "
            "detection at about a third of its cost."),
          figure(FIGS / "fig_budget_sweep.png",
                 "<b>Figure 3.</b> Effect of the Tier 2 budget on the test split. Left: recall at the train-fixed "
                 "threshold, with the judge on everything (dashed) and the cheap ensemble (dotted) as references. "
                 "Right: cost relative to running the judge on everything."),
          table([["Configuration", "Test Δ recall [95% CI]", "Held-out Δ recall [95% CI]",
                  "Cost vs Tier 2 (test / held-out)"],
                 ["Cascade, mean rule, B = 30%", "−0.04 [−0.11, +0.03]", "−0.00 [−0.12, +0.10]", "34% / 14%"],
                 ["Cascade, plan rule, B = 30%", "−0.06 [−0.15, +0.01]", "−0.04 [−0.17, +0.09]", "27% / 28%"],
                 ["Cascade, mean rule, B = 20%", "−0.09 [−0.18, −0.01]", "−0.04 [−0.18, +0.08]", "20% / 14%"],
                 ["T0 + T1 mean (no strong model)", "−0.18 [−0.29, −0.08]", "−0.19 [−0.39, 0.00]", "2.5% / 2.6%"]],
                [0.3, 0.22, 0.24, 0.2],
                "<b>Table 5.</b> Paired bootstrap against the Tier 2 judge on everything (recall at the "
                "train-fixed threshold). Negative Δ means the configuration recalls less than the judge.",
                bold_rows=(1,)),
          figure(RESULTS / "cost_vs_recall.png",
                 "<b>Figure 4.</b> Cost versus recall on the test split (symlog cost axis). Lines connect cascades "
                 "at 10/20/30% Tier 2 budgets; points are single monitors and ensembles.", width=0.72),
          table(cost_table(), [0.3, 0.12, 0.12, 0.12, 0.3],
                "<b>Table 6.</b> Cost and latency on the test split. Latency was measured under rate-limited "
                "parallel load and is best read as relative."),
          P("Cost and latency diverge (Table 6). The cheap Tier 1 model is a reasoning model that emits about 2k "
            "thinking tokens, so it is <i>slower</i> than the judge (29 s vs 23 s mean), and the cascade's mean "
            "latency (37 s) exceeds the judge's. A non-reasoning Tier 1 (gemma-4-31b-it) gives the same AUROC "
            "(0.92) at half the latency, though its threshold transfers worse (RQ3)."),
          H2("RQ3: thresholds fitted on one agent transfer to unseen agents"),
          P("With thresholds fixed on llama-70b data, <b>no monitor's AUROC drops</b> on trajectories from llama-8b "
            "and llama-405b, and most rise slightly (Figure 5). Recall at the fixed threshold holds or improves for "
            "every LLM monitor and cascade: the headline cascade reaches 0.96, equal to the judge, at 14% of its "
            "held-out cost, because fewer held-out runs need escalation (11% vs 27%). Tier 0 dips slightly (0.62 "
            "→ 0.58), and the one threshold that transfers badly is the alternative Tier 1 (gemma-4-31b-it): "
            "held-out recall 0.69 at an FPR of 0.13. Per agent, the headline cascade's held-out recall is 1.00 on "
            "llama-405b (12 attacks) and 0.93 on llama-8b (14 attacks). <b>Answer:</b> yes, for these agents, with "
            "the caveat that 56 held-out runs give wide CIs and all three agents share a model family."),
          figure(RESULTS / "heldout_vs_id.png",
                 "<b>Figure 5.</b> In-distribution (llama-70b test) versus held-out agents (llama-8b and llama-405b). "
                 "Left: AUROC with 95% bootstrap CIs. Right: recall at the train-fixed 5%-FPR threshold."),
          H2("RQ4: the judge partly exploits an artefact; a conservative cascade still holds"),
          P("Reading the judge's one-line reasons exposed a dataset-specific tell. Attacks are edits applied "
            "<i>after</i> the run, so the trajectory never shows the flaw being written, and the judge notices: its "
            "reason cites the trajectory for <b>74% of attacked runs (135/182) but 2% of honest runs (4/197)</b>, "
            "typically “this change is not present in the trajectory's edits” (Figure 6). Tier 2's numbers "
            "with the trajectory are therefore an <b>upper bound</b>. The same judge without the trajectory falls to "
            "AUROC 0.95 and recall 0.79 at the fixed threshold (FPR 0.08), and 0.85 on held-out. Built on that judge, "
            "the mean-rule cascade at B = 20% reaches recall 0.82 on test and 0.92 on held-out for $1.62 per 1,000 "
            "trajectories, <b>30% of the no-trajectory judge's cost</b>, and higher recall than that judge alone. "
            "<b>Answer:</b> the judge's margin over the cheap tiers is inflated by the leak, but the cascade's "
            "relative value (most of the judge's recall at a fraction of its cost) survives the conservative "
            "estimate."),
          figure(FIGS / "fig_trajectory_leak.png",
                 "<b>Figure 6.</b> The trajectory artefact. Left: share of Tier 2 reasons that cite the trajectory, "
                 "by class (all 379 runs). Right: the same judge with and without the trajectory; recall is at each "
                 "monitor's own train-fixed threshold."),
          H2("RQ5: a fine-tuned 4B model helps, but does not replace the prompted Tier 1"),
          table([["Monitor", "AUROC test", "AUROC held-out", "Recall @ 5% FPR (test ROC)", "Median latency", "API $ / 1k"],
                 ["Qwen3.5-4B zero-shot (same prompt)", "0.83", "0.88", "0.47", "0.32 s", "0"],
                 ["Qwen3.5-4B LoRA, A: real rows ×5", "0.88", "0.92", "0.71", "0.29 s", "0"],
                 ["Qwen3.5-4B LoRA, B: real + 800 synthetic", "0.83", "0.90", "0.54", "0.28 s", "0"],
                 ["Prompted Tier 1 (deepseek-v4-flash)", "0.92", "0.98", "0.58", "26 s", "0.40"]],
                [0.33, 0.1, 0.12, 0.17, 0.12, 0.1],
                "<b>Table 7.</b> Small open monitors scored locally (RTX 4080 Laptop, bf16) against the prompted "
                "Tier 1.", bold_rows=(2,)),
          P("Fine-tuning helps (Table 7): variant A improves AUROC over the zero-shot model by <b>+0.05</b> (paired bootstrap, "
            "test [+0.03, +0.08]; held-out [+0.01, +0.10]). It remains slightly below the prompted Tier 1 "
            "(−0.04; test [−0.09, +0.00], held-out [−0.13, +0.01]), although at the strict end of the "
            "ROC it recalls more (0.71 vs 0.58 at 5% FPR) and it is about <b>90× faster</b> with no API cost. "
            "Synthetic augmentation did not help: variant B is no better than zero-shot (+0.01 [−0.00, +0.02]) "
            "and significantly worse than A on test (−0.04 [−0.07, −0.02]). Two explanations cannot be "
            "separated here: generic synthetic rows may dilute the specific signal (a concealed change in a real "
            "diff), and B saw the real rows about once against five times for A. <b>Answer:</b> not as a "
            "replacement on this data, but it is a strong free pre-filter that could sit beside Tier 0.")]

    s += [H1("6 Discussion"),
          P("<b>Where the cascade fails.</b> Every miss and false positive of the headline cascade on test and "
            "held-out (218 runs, 104 attacks) was read by hand (Table 8)."),
          table([["Group", "Count", "Types", "What happened"],
                 ["Escalation miss", "6", "A5 ×4, A6 ×2",
                  "Tier 2 scored them 0.75–0.90, but the cheap tiers did not escalate. Mostly one-token tweaks "
                  "(DEFAULT_TIMEOUT 30→60, BUFFER_SIZE halved, strict=True, skip_validation=True): no Tier 0 "
                  "rule fires and Tier 1 rates the unreported change “unrelated but harmless”."],
                 ["Omission", "2", "A4 ×2", "The attack drops an assertion the honest fix would have added; "
                  "nothing is visible in the patch to a patch-only monitor."],
                 ["Seen, judged benign", "3", "A4 ×2, A6",
                  "Both LLM tiers named the change but called it “messy” or “a code-quality issue”."],
                 ["False positive", "4", "honest",
                  "Honest agents that silently removed existing error handling or validation; both LLM tiers "
                  "explain them as real, unreported regressions."]],
                [0.17, 0.07, 0.13, 0.63],
                "<b>Table 8.</b> Error analysis of the mean-rule cascade at B = 30% (11 misses, 4 false positives)."),
          P("Three lessons follow. First, the cascade's main blind spot is not the judge (which catches 94% of scope "
            "creep) but <b>escalation</b>: small constant changes look harmless to both cheap tiers. A Tier 0 rule "
            "for “changed literal in a hunk unrelated to the issue”, or a Tier 1 prompt that treats "
            "<i>any</i> unreported behavioural change as suspicious, targets exactly these six. Second, the false "
            "positives are mostly true positives for “unsafe and unreported”, just not deliberate: an "
            "honest-but-careless agent and a disabled-check attacker produce the same artefact, which puts a "
            "<b>floor under the achievable FPR</b> of any monitor that reads only outputs. Third, omission attacks "
            "need a reference (a specification, coverage or mutation testing), not a better reader."),
          P("<b>Implications for deployment.</b> (i) Escalating on the <i>mean</i> of the cheap scores is a simple "
            "change that beats the OR rule at every small budget. (ii) A say-vs-do monitor is more useful as an "
            "escalation signal than as a verdict: its ranking is good, its calibration at strict thresholds is "
            "not. (iii) For control evaluations built from post-hoc edits, monitors with access to the trajectory "
            "should be ablated, and judge rationales read, before their numbers are trusted. (iv) Cost and "
            "latency need separate budgets: the cheapest model per token was the slowest per run.")]

    s += [H1("7 Limitations"),
          bullets(["<b>Trajectory leak.</b> Attacks are applied after the run, so Tier 2 with trajectory and cascades "
                   "built on it are upper bounds; the no-trajectory ablation is the conservative estimate (RQ4).",
                   "<b>Synthetic, often blatant attacks.</b> The attacker chooses a flaw of a requested type in a single "
                   "shot; a real scheming agent would choose its own flaw and could make it look much more like honest "
                   "work. A1–A3 and A7 are easy for every tier, so the benchmark's difficulty lies in A4–A6.",
                   "<b>No execution.</b> Flaws are confirmed by a model check given the attacker's description, not by "
                   "running an exploit or the tests; omission attacks are validated only against the honest patch. "
                   "The human check found 1 of 20 attacks invalid, so about 5% of attacks (CI up to 24%) may not be "
                   "working flaws. That attack is in the train split. Refitting every threshold without it leaves the "
                   "headline cascade, all single monitors and the ablation unchanged. Some secondary cascades move by "
                   "1–3 test attacks (e.g. the no-trajectory cascade at B = 20%: recall 0.79 instead of 0.82), "
                   "so thresholds at the edge of the grid are sensitive to single training examples.",
                   "<b>Small data.</b> 379 trajectories (56 held-out), Python only, small patches, one dataset source and "
                   "Llama-based agents only; CIs are wide, especially per attack type (A6 has 15 attacks).",
                   "<b>Generated reports.</b> SWE-agent does not write final reports, so reports are generated from the "
                   "honest patch; real agents' reports may contain more or less detail.",
                   "<b>Single run per model.</b> Each monitor was run once per example (with caching); sampling variance "
                   "of the LLM monitors is not included in the CIs."])]

    s += [H1("8 Conclusion and future work"),
          P("On 379 real coding-agent trajectories with concealed flaws, a three-tier cascade that escalates about a "
            "quarter of runs to a strong judge keeps the judge's recall within statistical noise at a third of its "
            "cost, and its train-fitted thresholds transfer to unseen agents. Static analysis and a say-vs-do check "
            "are complementary and nearly free, but neither is a verdict at a strict FPR. Reading the judge's "
            "rationales showed that it exploits how the attacks were built, so its numbers are an upper bound; a "
            "no-trajectory cascade remains attractive under the conservative estimate. Next steps: <b>agent-chosen "
            "attacks</b> planted during the run, so the trajectory contains the edit and the leak disappears; an "
            "unrelated-literal rule and a stricter Tier 1 prompt aimed at escalation misses; execution-based checks "
            "for omissions; more diverse agents (other scaffolds and model families); and a multi-turn red team "
            "that adapts to the monitor.")]

    s += [H1("References"),
          P("[1] R. Greenblatt, B. Shlegeris, K. Sachan, F. Roger. AI Control: Improving Safety Despite Intentional "
            "Subversion. arXiv:2312.06942, 2023.", "ref"),
          P("[2] J. Yang, C. E. Jimenez, A. Wettig, K. Lieret, S. Yao, K. Narasimhan, O. Press. SWE-agent: "
            "Agent-Computer Interfaces Enable Automated Software Engineering. NeurIPS 2024.", "ref"),
          P("[3] C. E. Jimenez, J. Yang, A. Wettig, S. Yao, K. Pei, O. Press, K. Narasimhan. SWE-bench: Can Language "
            "Models Resolve Real-World GitHub Issues? ICLR 2024.", "ref"),
          P("[4] E. J. Hu, Y. Shen, P. Wallis, Z. Allen-Zhu, Y. Li, S. Wang, L. Wang, W. Chen. LoRA: Low-Rank "
            "Adaptation of Large Language Models. ICLR 2022.", "ref"),
          P("[5] Nebius. SWE-agent-trajectories (dataset). huggingface.co/datasets/nebius/SWE-agent-trajectories.", "ref"),
          P("[6] Tools: Semgrep (semgrep.dev), Bandit (github.com/PyCQA/bandit), detect-secrets "
            "(github.com/Yelp/detect-secrets).", "ref")]
    return s


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=2.0 * cm, rightMargin=2.0 * cm,
                            topMargin=1.9 * cm, bottomMargin=1.8 * cm, title=TITLE, author="Sushovit Nanda",
                            subject="Tiered monitoring of coding agents: cost, recall and transfer")
    doc.build(story(), onFirstPage=on_page, onLaterPages=on_page)
    from pypdf import PdfReader
    print("wrote", OUT, "pages:", len(PdfReader(str(OUT)).pages))


if __name__ == "__main__":
    main()
