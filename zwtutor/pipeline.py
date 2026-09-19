"""question -> pre-check -> retrieve -> evidence gate -> generate -> verify -> result.

The State is decided here, in code. The model can only say "cannot answer" or "conflict"; both
are re-checked. Nothing reaches the learner as GROUNDED unless its quotes and numbers verified.
"""
from __future__ import annotations

import re
from typing import Optional

from . import messages as M
from .gate import GateConfig, decide
from .generate import Generator, build_prompt
from .models import CitationView, Evidence, State, TutorResult
from .retrieve import Retriever
from .safety import precheck
from .schema import MODES, build_schema
from .verify import ClaimResult, VClaim, claim_overlap, unsupported_numbers, verify_claim, verify_memory_aid


class Tutor:
    def __init__(self, index, embedder, generator: Optional[Generator], cfg: Optional[GateConfig] = None,
                 strict: bool = True, k: int = 6):
        self.index, self.embedder, self.generator = index, embedder, generator
        self.cfg = cfg or GateConfig()
        self.strict = strict
        self.retriever = Retriever(index, embedder, k=k)

    # ------------------------------------------------------------------ helpers
    def _res(self, state, mode, msg="", **kw) -> TutorResult:
        return TutorResult(state=state, mode=mode, message=msg, **kw)

    @staticmethod
    def _views(cr: ClaimResult) -> list[CitationView]:
        return [CitationView(c["chunk"], c["quote"], c["verified"], cr.text) for c in cr.citations if c["chunk"] is not None]

    # ------------------------------------------------------------------ main entry
    def ask(self, question: str, mode: str = "explain") -> TutorResult:
        if mode not in MODES:
            mode = "explain"
        pre = precheck(question)
        notes = [M.OVERRIDE_NOTICE] if "override_attempt" in pre.flags else []
        if pre.state is not None:  # refused before ANY retrieval or model call
            return self._res(pre.state, mode, pre.message, flags=pre.flags, limitations=notes)

        ev: Evidence = self.retriever.search(question)
        gd = decide(ev, self.cfg)
        gate = {"passed": gd.passed, "reason": gd.reason, "top_sem": round(gd.top_sem, 3), "top_cov": round(gd.top_cov, 3),
                "tau_sem": self.cfg.tau_sem, "tau_cov": self.cfg.tau_cov, "calibrated": self.cfg.calibrated}
        if not gd.passed:
            return self._res(State.NOT_IN_CORPUS, mode, M.NOT_IN_CORPUS, evidence=ev.hits[:3], gate=gate,
                             flags=pre.flags, limitations=notes)
        if mode == "source":  # no generation at all
            return self._res(State.GROUNDED, mode, "", evidence=gd.hits, gate=gate, flags=pre.flags, limitations=notes)

        allowed_hits = gd.hits
        allowed = {h.chunk.chunk_id for h in allowed_hits}
        schema = build_schema(mode, sorted(allowed))
        raw, model = self.generator.generate(build_prompt(question, mode, allowed_hits), schema)
        base = dict(gate=gate, flags=pre.flags, model_used=model, generated=True, evidence=allowed_hits)

        if raw.get("cannot_answer"):
            return self._res(State.NOT_IN_CORPUS, mode, M.NOT_IN_CORPUS, **base, limitations=notes)
        return self._verify_and_build(raw, mode, allowed, base, notes)

    # ------------------------------------------------------------------ verification
    def _verify_and_build(self, raw: dict, mode: str, allowed: set, base: dict, notes: list[str]) -> TutorResult:
        by_id = self.index.by_id
        limitations = list(notes) + [str(x) for x in (raw.get("limitations") or [])][:3]
        problems: list[str] = []

        def run(text, cites, kind):
            r = verify_claim(VClaim(text, cites or [], kind), by_id, allowed)
            if not r.verified:
                problems.append(f"{kind}: {'; '.join(r.problems)}")
            return r

        pts_raw = [p for p in (raw.get("points") or []) if isinstance(p, dict)]
        pts = [run(str(p.get("text", "")), p.get("citations"), "point") for p in pts_raw]

        quiz, cards = [], []
        for q in raw.get("quiz") or []:
            ans = str(q.get("answer", ""))
            if mode == "exam" and ans not in [str(o) for o in q.get("options", [])]:
                problems.append("exam: the correct answer is not one of the options")
                quiz.append({"q": q, "res": None, "ok": False})
                continue
            r = run(f"{ans} {q.get('explanation', '')}".strip(), q.get("citations"), "quiz")
            quiz.append({"q": q, "res": r, "ok": r.verified})
        for c in raw.get("cards") or []:
            r = run(f"{c.get('front', '')} {c.get('back', '')}", c.get("citations"), "card")
            cards.append({"c": c, "res": r, "ok": r.verified})

        # the one-line summary has no citations of its own: it may not introduce numbers or unrelated words
        summary = str(raw.get("summary") or "").strip()
        good_chunks = [c["chunk"] for r in pts for c in r.citations if c["verified"]]
        if summary:
            if not good_chunks:
                summary = ""
            elif unsupported_numbers(summary, good_chunks) or claim_overlap(summary, good_chunks) < 0.5:
                problems.append("summary: contains numbers or words not found in the cited text")
                summary = ""

        scenario = str(raw.get("scenario") or "").strip()
        if scenario and re.search(r"\d", scenario):
            scenario = ""
            limitations.append("The invented scenario was removed because it contained numbers.")

        need = {"quiz": bool(quiz), "exam": bool(quiz), "flashcards": bool(cards)}.get(mode, bool(pts))
        any_verified = any(r.verified for r in pts) or any(x["ok"] for x in quiz) or any(x["ok"] for x in cards)
        vsum = {"claims": len(pts) + len(quiz) + len(cards), "failed": len(problems), "problems": problems}

        if not need or not any_verified or (self.strict and problems):
            return self._res(State.CANNOT_VERIFY, mode, M.CANNOT_VERIFY, **base, verification=vsum, limitations=limitations)

        # non-strict mode keeps only claims that verified
        all_pts = pts  # the model numbered its memory-aid letters against THIS list
        newidx, k = {}, 0
        for i, r in enumerate(all_pts):
            if r.verified:
                newidx[i] = k
                k += 1
        pts = [r for r in all_pts if r.verified]
        points = [{"text": r.text, "citations": self._views(r), "verified": True} for r in pts]
        quiz_out = [{**x["q"], "citations": self._views(x["res"])} for x in quiz if x["ok"]]
        cards_out = [{**x["c"], "citations": self._views(x["res"])} for x in cards if x["ok"]]

        aid = None
        if mode == "mnemonic":
            aid, why = verify_memory_aid(raw.get("memory_aid"), all_pts)
            if aid is not None:  # renumber to the points actually shown
                for l in aid["letters"]:
                    l["point_index"] = newidx[l["point_index"]]
            if aid is None:
                limitations.append(f"No memory aid is shown: {why or 'none was produced'}.")

        withheld = len([p for p in problems if not p.startswith("summary")])
        vsum["withheld"] = withheld
        if withheld:  # verified-only mode: shown claims all verified, the rest are held back and the learner is told
            limitations.append(f"{withheld} point(s) were withheld because their quote or numbers could not be verified against the source, "
                               "so this answer may be incomplete. Use the source links, or switch on Strict verification in Sources > Settings.")
        result = self._res(State.GROUNDED, mode, "", **base, answer=summary, points=points, memory_aid=aid,
                           quiz=quiz_out, cards=cards_out, limitations=limitations, verification=vsum)
        if scenario:
            result.answer = (result.answer + "\n\n" if result.answer else "") + "Invented teaching scenario (not from the sources): " + scenario

        conflict = raw.get("conflict") or {}
        if conflict.get("exists"):
            sources = {c.chunk.source_id for p in points for c in p["citations"] if c.verified}
            if len(sources) >= 2:
                result.state = State.CONFLICTING_SOURCES
                result.message = M.CONFLICTING_SOURCES
                result.conflict = {"description": str(conflict.get("description", "")), "sources": sorted(sources)}
            else:
                result.limitations.append("The model suggested a conflict, but it could not be shown from two verified sources, so it is not reported.")
        return result
