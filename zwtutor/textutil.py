"""Text helpers shared by ingestion, retrieval and verification."""
from __future__ import annotations

import re
import unicodedata

_QUOTES = {"‘": "'", "’": "'", "‚": "'", "“": '"', "”": '"', "„": '"'}
_DASHES = {"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-"}
_BULLETS = "•▪●○◦■□◆►‣⁃"
_BULLET_RE = re.compile(rf"(?:(?<=\s)|^)[{re.escape(_BULLETS)}](?=\s|$)")
_SOFT_HYPHEN = "­"


def _base(s: str) -> str:
    """Remove PDF extraction noise only: never changes words."""
    s = unicodedata.normalize("NFKC", s or "")
    s = s.replace(_SOFT_HYPHEN, "").replace(" ", " ")
    for a, b in {**_QUOTES, **_DASHES}.items():
        s = s.replace(a, b)
    s = _BULLET_RE.sub(" ", s)
    return s


def quote_forms(s: str) -> tuple[str, str]:
    """Two comparable forms of a text.

    (joined, kept): a word split by a hyphen at a line break is either joined
    ("antiretroviral") or kept as a hyphenated compound ("anti-retroviral"), because the
    extracted text cannot tell which the author meant. A quote matches if it is in either.
    Case, punctuation and every word are preserved; only whitespace is collapsed.
    """
    s = _base(s)
    joined = re.sub(r"(\w)-[ \t]*\n[ \t]*(\w)", r"\1\2", s)
    kept = re.sub(r"(\w)-[ \t]*\n[ \t]*(\w)", r"\1-\2", s)
    collapse = lambda t: " ".join(t.split())  # noqa: E731
    return collapse(joined), collapse(kept)


def normalise_quote(s: str) -> str:
    return quote_forms(s)[0]


STOPWORDS = set(
    """a an and are as at be been but by can could did do does for from had has have how i if in into is it its
    me my of on or our should so than that the their them then there these they this to was we were what when where
    which who whom why will with would you your about after before during give given tell explain describe list
    please much many any some between""".split()
)

_TOKEN_RE = re.compile(r"\d+(?:[.,]\d+)?|[a-z][a-z\-']*[a-z]|[a-z]", re.I)


def stem(w: str) -> str:
    """Very light stemmer (plural / -ing / -ed), enough for term matching."""
    w = w.lower().strip("-'")
    for suf in ("ations", "ation", "ings", "ing", "ies", "es", "ed", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)] + ("y" if suf == "ies" else "")
    return w


def tokens(s: str) -> list[str]:
    return [t.lower().replace(",", ".") for t in _TOKEN_RE.findall(_base(s))]


def content_terms(s: str) -> list[str]:
    """Stemmed, de-duplicated content words (numbers kept) in first-seen order."""
    seen, out = set(), []
    for t in tokens(s):
        if t in STOPWORDS:
            continue
        st = t if t[0].isdigit() else stem(t)
        if st not in seen and len(st) > 1:
            seen.add(st)
            out.append(st)
    return out
