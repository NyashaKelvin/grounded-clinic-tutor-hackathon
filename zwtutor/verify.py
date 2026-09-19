"""Independent verification of model output. Nothing here trusts the model.

- verify_quote:     the quote must appear, contiguously, in the cited chunk's extracted text.
- numbers:          every clinically meaningful number in a claim must appear, with the same
                    unit, in the chunk(s) the claim cites. No conversion, no arithmetic.
- claim overlap:    a rough check that the claim's key words appear in the cited text.
- memory aids:      each letter must map to a verified teaching point and its words.

Verification proves a quote EXISTS and that numbers are PRINTED in the source. It does not prove
that the explanation faithfully reflects the passage (see README limitations).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Iterable, Optional

from .models import Chunk
from .textutil import content_terms, quote_forms, stem

MIN_QUOTE_WORDS = 5
CLAIM_OVERLAP_MIN = 0.5  # heuristic, tune on the evaluation set

# ------------------------------------------------------------------ quotes
def verify_quote(chunk: Optional[Chunk], quote: str) -> tuple[bool, str]:
    if chunk is None:
        return False, "unknown chunk id"
    q = quote_forms(quote)[0]
    if len(q.split()) < MIN_QUOTE_WORDS:
        return False, f"quote too short (< {MIN_QUOTE_WORDS} words)"
    joined, kept = quote_forms(chunk.source_text)
    if q in joined or q in kept:
        return True, "ok"
    # the quote may itself contain a line-break hyphen variant
    qk = quote_forms(quote)[1]
    if qk in joined or qk in kept:
        return True, "ok"
    return False, "quote not found in the cited chunk"


def locate_quote(raw_text: str, quote: str) -> Optional[tuple[int, int]]:
    """Character span of the quote inside the raw chunk text (for highlighting), or None."""
    words = quote.split()
    if not words:
        return None
    def word_rx(w: str) -> str:
        # tolerate a line-break hyphen inside a word ("temp-\nerature")
        return r"(?:-\s*)?".join(re.escape(ch) for ch in w)
    pattern = r"\s+".join(word_rx(w) for w in words)
    m = re.search(pattern, raw_text)
    return (m.start(), m.end()) if m else None


# ------------------------------------------------------------------ numbers
_NUMWORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20, "thirty": 30, "forty": 40,
             "fifty": 50, "sixty": 60}
_UNIT_CORE = (r"mcg|µg|ug|mg|g|kg|ml|mls|l|litres?|liters?|iu|units?|%|percent|mmhg|mmol|mol|meq|cells|copies|"
              r"weeks?|days?|months?|years?|yrs?|hours?|hrs?|hourly|h|minutes?|mins?|seconds?|secs?|°c|°f|degrees?|"
              r"times|doses?|tablets?|capsules?|drops?|bpm|breaths|beats|sachets?|vials?|ampoules?")
_UNIT_DEN = r"kg|ml|l|dl|mm3|mm|min|day|dose|hr|h|week|month|24\s*hours?|hours?|minutes?"
_UNIT = rf"(?:{_UNIT_CORE})(?:\s*(?:/|per)\s*(?:{_UNIT_DEN}))*"
_NUM = r"\d+(?:[.,]\d+)?"

_FREQ = [
    (re.compile(r"\b(?:once (?:a |per |every )?(?:day|daily)|once daily|o\.?d\.?)\b", re.I), "1"),
    (re.compile(r"\b(?:twice (?:a |per |every )?(?:day|daily)|twice daily|b\.?d\.?|b\.?i\.?d\.?)\b", re.I), "2"),
    (re.compile(r"\b(?:three times (?:a |per |every )?(?:day|daily)|t\.?d\.?s\.?|t\.?i\.?d\.?)\b", re.I), "3"),
    (re.compile(r"\b(?:four times (?:a |per |every )?(?:day|daily)|q\.?d\.?s\.?|q\.?i\.?d\.?)\b", re.I), "4"),
]

_MASTER = re.compile(
    rf"(?P<pair>(?<![\d./]){_NUM.replace('[.,]', '.')}/\d{{1,3}}(?![\d/]))(?:\s*(?P<pairunit>mmhg))?"
    rf"|(?<![A-Za-z\d.,/])(?P<n1>{_NUM})(?:\s*(?:-|to)\s*(?P<n2>{_NUM}))?(?:\s*-?\s*(?P<unit>{_UNIT})(?![A-Za-z]))?",
    re.I)

_LABEL_BEFORE = re.compile(r"(?:step|steps|table|figure|fig|page|pages|chapter|section|point|item|no|#)\.?\s*$", re.I)


@dataclass(frozen=True)
class Qty:
    value: str  # canonical, e.g. "2.5", "5-10", "140/90", or freq token "1" with unit "per-day"
    unit: str  # canonical unit or "" for a bare number
    raw: str

    def key(self) -> tuple[str, str]:
        return (self.value, self.unit)


def _canon_num(s: str) -> str:
    try:
        d = Decimal(s.replace(",", "."))
    except InvalidOperation:
        return s
    txt = format(d.normalize(), "f")
    return txt


def _canon_unit(u: str) -> str:
    u = re.sub(r"\s+", "", u.lower()).replace("per", "/")
    subs = [(r"^(µg|ug|mcg)", "mcg"), (r"^mls\b", "ml"), (r"^(litres?|liters?)", "l"), (r"^percent", "%"),
            (r"^(hours?|hrs?|hourly|h)(?=/|$)", "hour"), (r"^(minutes?|mins?)(?=/|$)", "minute"),
            (r"^(seconds?|secs?)(?=/|$)", "second"), (r"^days?(?=/|$)", "day"), (r"^weeks?(?=/|$)", "week"),
            (r"^months?(?=/|$)", "month"), (r"^(years?|yrs?)(?=/|$)", "year"), (r"^tablets?", "tablet"),
            (r"^capsules?", "capsule"), (r"^units?", "unit"), (r"^doses?", "dose"), (r"^drops?", "drop"),
            (r"^(degrees?|°c)", "°c"), (r"^mm3", "mm3")]
    for pat, rep in subs:
        u = re.sub(pat, rep, u)
    u = re.sub(r"/(hours?|hrs?|h)$", "/hour", u)
    u = re.sub(r"/24hours?", "/day", u)
    return u


def _prep(text: str) -> str:
    """Normalise dashes, convert number words that precede a unit, drop ordinals/list numbering."""
    t = text.replace("–", "-").replace("—", "-").replace("−", "-")
    t = re.sub(r"(?m)^\s*\(?\d{1,2}[.)]\s+", "", t)  # list numbering at line start
    t = re.sub(rf"\b(\d+)(?:st|nd|rd|th)\b", " ", t, flags=re.I)  # ordinals: 7th edition
    words = "|".join(_NUMWORDS)
    t = re.sub(rf"\b({words})\b(?=[\s-]*(?:{_UNIT})\b)", lambda m: str(_NUMWORDS[m.group(1).lower()]), t, flags=re.I)
    return t


def extract_quantities(text: str) -> list[Qty]:
    out: list[Qty] = []
    t = _prep(text or "")
    for rx, val in _FREQ:
        for m in rx.finditer(t):
            out.append(Qty(val, "per-day", m.group(0)))
    for m in _MASTER.finditer(t):
        raw = m.group(0).strip()
        if m.group("pair"):
            out.append(Qty(m.group("pair"), "mmhg" if m.group("pairunit") else "", raw))
            continue
        n1, n2, unit = m.group("n1"), m.group("n2"), m.group("unit")
        if not unit:
            nxt = t[m.end(): m.end() + 1]
            if nxt.isalpha():  # 3TC, 5FU etc: a drug code, not a quantity
                continue
            before = t[max(0, m.start() - 12): m.start()]
            if _LABEL_BEFORE.search(before):
                continue
            if n2 is None and re.fullmatch(r"(19[5-9]\d|20\d\d)", n1):  # a year
                continue
        val = _canon_num(n1) if n2 is None else f"{_canon_num(n1)}-{_canon_num(n2)}"
        out.append(Qty(val, _canon_unit(unit) if unit else "", raw))
    return out


def _source_index(chunks: Iterable[Chunk]) -> tuple[set, set]:
    keys, values = set(), set()
    for c in chunks:
        for q in extract_quantities(c.source_text):
            keys.add(q.key())
            values.add(q.value)
        # a bare token match is also acceptable for unit-less numbers
        for tok in re.findall(_NUM, _prep(c.source_text)):
            values.add(_canon_num(tok))
    return keys, values


def unsupported_numbers(text: str, chunks: Iterable[Chunk]) -> list[str]:
    """Numbers stated in `text` that are not printed (same value, same unit) in `chunks`."""
    chunks = list(chunks)
    keys, values = _source_index(chunks)
    bad: list[str] = []
    for q in extract_quantities(text):
        if q.unit:
            ok = q.key() in keys
        else:
            ok = q.value in values
        if not ok:
            bad.append(q.raw)
    return bad


# ------------------------------------------------------------------ claim overlap
def claim_overlap(text: str, chunks: Iterable[Chunk]) -> float:
    terms = content_terms(text)
    if not terms:
        return 1.0
    have: set[str] = set()
    for c in chunks:
        have |= set(content_terms(c.source_text + " " + c.section))
    return sum(1 for t in terms if t in have) / len(terms)


# ------------------------------------------------------------------ verification of a whole model output
@dataclass
class VClaim:
    text: str
    citations: list[dict]  # [{"chunk_id","quote"}]
    kind: str = "point"


@dataclass
class ClaimResult:
    text: str
    verified: bool
    citations: list[dict]  # [{"chunk","quote","verified","reason"}]
    problems: list[str] = field(default_factory=list)
    overlap: float = 1.0


def verify_claim(claim: VClaim, by_id: dict[str, Chunk], allowed: set[str]) -> ClaimResult:
    cites, good_chunks, problems = [], [], []
    for c in claim.citations:
        cid = c.get("chunk_id", "")
        chunk = by_id.get(cid) if cid in allowed else None
        ok, why = verify_quote(chunk, c.get("quote", ""))
        cites.append({"chunk": chunk, "chunk_id": cid, "quote": c.get("quote", ""), "verified": ok, "reason": why})
        if ok:
            good_chunks.append(chunk)
        else:
            problems.append(f"citation {cid or '?'}: {why}")
    if not claim.citations:
        problems.append("no citation")
    if not good_chunks:
        return ClaimResult(claim.text, False, cites, problems or ["no verified citation"], 0.0)
    bad_nums = unsupported_numbers(claim.text, good_chunks)
    if bad_nums:
        problems.append(f"numbers not in the cited text: {', '.join(bad_nums)}")
    ov = claim_overlap(claim.text, good_chunks)
    if ov < CLAIM_OVERLAP_MIN:
        problems.append(f"claim words mostly absent from the cited text (overlap {ov:.2f})")
    return ClaimResult(claim.text, not bad_nums and ov >= CLAIM_OVERLAP_MIN, cites, problems, ov)


def verify_memory_aid(aid: Optional[dict], points: list[ClaimResult]) -> tuple[Optional[dict], str]:
    """Returns (checked_aid or None, reason if dropped). Every letter must map to a verified point."""
    if not aid:
        return None, ""
    text = str(aid.get("text", "")).strip()
    letters = aid.get("letters") or []
    if not text or not letters:
        return None, "memory aid incomplete"
    if re.search(r"\d", text) or any(re.search(r"\d", str(l.get("stands_for", ""))) for l in letters):
        return None, "memory aid contains digits (not allowed)"
    acronym = re.sub(r"[^A-Za-z]", "", text)
    if len(acronym) != len(letters):
        return None, "acronym length does not match its letters"
    out = []
    for ch, l in zip(acronym, letters):
        stands = str(l.get("stands_for", "")).strip()
        idx = l.get("point_index")
        if not stands or stands[0].lower() != ch.lower():
            return None, f"letter {ch} does not start '{stands}'"
        if not isinstance(idx, int) or not (0 <= idx < len(points)) or not points[idx].verified:
            return None, f"letter {ch} is not tied to a verified teaching point"
        pt_terms = set(content_terms(points[idx].text))
        for term in content_terms(stands):
            if term not in pt_terms and stem(term) not in pt_terms:
                return None, f"'{stands}' is not a word from teaching point {idx + 1}"
        out.append({"letter": ch.upper(), "stands_for": stands, "point_index": idx})
    return {"text": text, "letters": out}, ""
