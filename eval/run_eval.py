"""Run the evaluation set.

  python eval/run_eval.py --no-generate     # retrieval + gate + pre-check only (embedding calls only)
  python eval/run_eval.py                   # full pipeline with Gemini generation

Writes eval/results_<mode>.json and prints a summary. Grounded questions are counted only when
"labelled": true (a human confirmed the passage exists and filled expected_chunk_ids).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zwtutor import runtime  # noqa: E402
from zwtutor.models import State  # noqa: E402


class _Stop(Exception):
    pass


class _NoGen:
    def generate(self, prompt, schema):
        raise _Stop()


def load_questions(path: Path = ROOT / "eval" / "questions.jsonl") -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]


def run(tutor, questions: list[dict], generate: bool) -> list[dict]:
    if not generate:
        tutor.generator = _NoGen()
    out = []
    for q in questions:
        try:
            r = tutor.ask(q["question"], q.get("mode", "explain"))
            state, gate, gen = r.state.value, r.gate, r.generated
            hit_ids = [h.chunk.chunk_id for h in r.evidence]
            problems = r.verification.get("problems", [])
        except _Stop:  # gate passed, generation deliberately skipped
            ev = tutor.retriever.search(q["question"])
            state, gate, gen = "GATE_PASSED", {"top_sem": ev.top_sem, "top_cov": ev.top_cov}, False
            hit_ids, problems = [h.chunk.chunk_id for h in ev.hits], []
        exp = q.get("expected_chunk_ids") or []
        out.append({**{k: q[k] for k in ("id", "category", "question", "expect_state", "labelled")},
                    "state": state, "gate": gate, "generated": gen, "top_ids": hit_ids[:6],
                    "hit_at_k": bool(set(exp) & set(hit_ids)) if exp else None, "problems": problems})
    return out


def summarise(rows: list[dict]) -> dict:
    s: dict = {}
    ungr = [r for r in rows if r["category"] in ("ungrounded", "citation_trap", "ambiguous", "adversarial")]
    answered_wrongly = [r for r in ungr if r["state"] in ("GROUNDED", "GATE_PASSED") and r["expect_state"] != "GROUNDED"]
    s["should_refuse_total"] = len(ungr)
    s["should_refuse_but_passed"] = [r["id"] for r in answered_wrongly]
    gr = [r for r in rows if r["category"] == "grounded" and r["labelled"]]
    s["grounded_labelled"] = len(gr)
    s["grounded_refused"] = [r["id"] for r in gr if r["state"] not in ("GROUNDED", "GATE_PASSED")]
    lab = [r for r in gr if r["hit_at_k"] is not None]
    s["retrieval_hit_at_k"] = (sum(1 for r in lab if r["hit_at_k"]) / len(lab)) if lab else None
    s["adversarial_reached_gate"] = [r["id"] for r in rows if r["category"] == "adversarial" and r["state"] == "GATE_PASSED"]
    s["states"] = dict(Counter(r["state"] for r in rows))
    s["state_matches_expected"] = sum(1 for r in rows if r["state"] == r["expect_state"]) / max(1, len(rows))
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-generate", action="store_true")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass
    try:
        t = runtime.load_tutor(runtime.get_key())
    except runtime.SetupError as exc:
        print(exc)
        return 2
    rows = run(t, load_questions(), generate=not a.no_generate)
    summ = summarise(rows)
    name = "retrieval" if a.no_generate else "full"
    (ROOT / "eval" / f"results_{name}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=2), encoding="utf-8")
    print(json.dumps(summ, indent=2))
    if not t.cfg.calibrated:
        print("\nNOTE: thresholds are uncalibrated placeholders; run eval/calibrate.py after labelling the grounded questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
