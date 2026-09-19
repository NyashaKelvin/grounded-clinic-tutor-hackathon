"""Choose the evidence-gate thresholds from LABELLED data, with a tuning/held-out split.

Uses only retrieval (embedding calls; no answer generation). Needs >= 4 labelled grounded and >= 4 ungrounded questions.
Rule: on the tuning half, choose the thresholds that refuse EVERY ungrounded question (zero false passes) and keep the
most grounded questions; ties -> the lower (more permissive) pair that still refuses all. Then report on the held-out half.
With ~30 questions this is a small-sample estimate: report it as such, do not present it as proven accuracy.
"""
from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_eval import load_questions  # noqa: E402
from zwtutor import runtime  # noqa: E402
from zwtutor.gate import GateConfig, save_config  # noqa: E402


def choose(pos: list[tuple[float, float]], neg: list[tuple[float, float]], grid_sem, grid_cov):
    """pos = (sem, cov) of grounded questions, neg = of ungrounded. Returns (tau_sem, tau_cov, kept_pos, passed_neg)."""
    best = None
    for ts, tc in itertools.product(grid_sem, grid_cov):
        passed_neg = sum(1 for s, c in neg if s >= ts and c >= tc)
        kept = sum(1 for s, c in pos if s >= ts and c >= tc)
        key = (-passed_neg, kept, -(ts + tc))
        if best is None or key > best[0]:
            best = (key, ts, tc, kept, passed_neg)
    return best[1], best[2], best[3], best[4]


def stats(tutor, qs):
    out = []
    for q in qs:
        ev = tutor.retriever.search(q["question"])
        out.append((ev.top_sem, ev.top_cov))
    return out


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    try:
        t = runtime.load_tutor(runtime.get_key())
    except runtime.SetupError as exc:
        print(exc)
        return 2
    qs = [q for q in load_questions() if q["labelled"] and q["category"] in ("grounded", "ungrounded")]
    tune = qs[0::2]
    held = qs[1::2]
    split = lambda part: ([q for q in part if q["category"] == "grounded"], [q for q in part if q["category"] == "ungrounded"])  # noqa: E731
    (tp, tn), (hp, hn) = split(tune), split(held)
    if min(len(tp), len(tn), len(hp), len(hn)) < 2:
        print("Not enough labelled questions in each half. Label the grounded questions in eval/questions.jsonl first.")
        return 3
    grid_s = [round(x * 0.02, 2) for x in range(15, 46)]
    grid_c = [round(x * 0.1, 1) for x in range(0, 11)]
    ts, tc, kept, fp = choose(stats(t, tp), stats(t, tn), grid_s, grid_c)
    hps, hns = stats(t, hp), stats(t, hn)
    held_kept = sum(1 for s, c in hps if s >= ts and c >= tc)
    held_fp = sum(1 for s, c in hns if s >= ts and c >= tc)
    report = {"tau_sem": ts, "tau_cov": tc, "tuning": {"grounded_kept": f"{kept}/{len(tp)}", "ungrounded_passed": f"{fp}/{len(tn)}"},
              "held_out": {"grounded_kept": f"{held_kept}/{len(hp)}", "ungrounded_passed": f"{held_fp}/{len(hn)}"},
              "embedder": t.index.meta.get("embedder")}
    print(json.dumps(report, indent=2))
    save_config(GateConfig(tau_sem=ts, tau_cov=tc, calibrated=True), note=json.dumps(report))
    print("Wrote eval/thresholds.json. Report the held-out numbers honestly; the sample is small.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
