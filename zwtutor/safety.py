"""Deterministic pre-checks that run BEFORE retrieval or any model call.

The pattern lists are a first version. NEEDS REVIEW by a nurse educator before real use
(emergency terms), and the Zimbabwean ID-number pattern needs confirming.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from . import messages as M
from .models import State
from .textutil import content_terms

_I = re.I

# --- privacy ---------------------------------------------------------------------------
PII_PATTERNS = {
    "phone number": re.compile(r"(?:(?<!\d)\+?263[\s\-]?|(?<!\d)0)7[1-9][\s\-]?\d{3}[\s\-]?\d{3,4}(?!\d)"),
    "phone number (long digits)": re.compile(r"(?<![\d.])\+?\d[\d\s\-]{9,}\d(?![\d.])"),
    "email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "national ID number": re.compile(r"\b\d{2}[\s\-]?\d{6,7}[\s\-]?[A-Za-z][\s\-]?\d{2}\b"),  # format to be confirmed
    "patient name": re.compile(r"\b(?i:patient|pt|baby of|mrs?|ms|miss|master|mama|sekuru)\.?\s+[A-Z][a-z]{2,}\b"),
    "hospital / patient number": re.compile(r"\b(?:hosp(?:ital)?|patient|file|reg(?:istration)?|mrn|op|ip)\s*(?:no|number|#|num)\.?\s*[:#]?\s*\d{3,}", _I),
    "street address": re.compile(r"\b\d{1,5}\s+[A-Z][a-z]+\s+(?:street|st|road|rd|avenue|ave|drive|crescent)\b", _I),
}

# --- emergencies: a live situation, not a study question --------------------------------
_EMERGENCY_TERMS = re.compile(
    r"\b(cardiac arrest|not breathing|stopped breathing|no pulse|unresponsive|unconscious|choking|seizing|"
    r"having a (?:seizure|fit)|fitting|eclamptic fit|convulsing|massive bleeding|heavy bleeding|haemorrhaging|hemorrhaging|"
    r"anaphyla\w+|collapsed|overdosed|overdose|turning blue|cyanosed)\b", _I)
_LIVE_MARKERS = re.compile(
    r"\b(my patient|the patient is|patient is|she is|he is|she's|he's|baby is|child is|mother is|right now|now|currently|"
    r"just now|urgent(?:ly)?|help|what do i do)\b", _I)

# --- out of scope -----------------------------------------------------------------------
_PATIENT_MARKER = re.compile(
    r"\b(my patient|this patient|our patient|the patient|a patient who|patient is|he is|she is|weighs|weighing|"
    r"\d+(?:\.\d+)?\s?(?:kg|kilograms?)|\d+\s?(?:years?|yrs?|months?|weeks?|days?)[\s-]?old)\b", _I)
_DOSE_INTENT = re.compile(
    r"\b(how much|how many (?:mg|ml|mls|tablets|drops)|what dose|dose (?:should|do|can) (?:i|we)|should i give|"
    r"calculate (?:the )?dose|dosage for (?:my|this))\b", _I)
_DIAGNOSIS = re.compile(
    r"\b(diagnose|what (?:does|do) (?:my|this|the) patient have|what is wrong with (?:my|this) patient|"
    r"differential (?:diagnosis )?for my)\b", _I)
_PRESCRIBE = re.compile(r"\b(prescribe|write (?:a )?prescription|what should i prescribe)\b", _I)
_FABRICATE = re.compile(
    r"\b(make up|invent|fabricate|pretend (?:that )?(?:the )?(?:guideline|guidelines|protocol|source|document)|"
    r"imagine (?:that )?the guideline says|say the guideline says)\b", _I)
_OVERRIDE = re.compile(
    r"(ignore (?:your|the|all|any)[\w\s]{0,25}(?:sources?|documents?|rules|instructions|guidelines|material)|"
    r"answer from your (?:own )?(?:medical )?(?:knowledge|training)|even if it isn'?t in|even if (?:it is|it's) not in|"
    r"don'?t cite|do not cite|without (?:citing|citations|sources)|no citations?)", _I)


@dataclass
class PreCheck:
    state: Optional[State] = None  # None = continue to retrieval
    message: str = ""
    flags: list[str] = field(default_factory=list)
    pii_kinds: list[str] = field(default_factory=list)


def find_pii(text: str) -> list[str]:
    kinds = []
    for kind, rx in PII_PATTERNS.items():
        if rx.search(text) and kind not in kinds:
            # the two phone patterns describe the same thing
            if kind == "phone number (long digits)" and "phone number" in kinds:
                continue
            kinds.append(kind)
    return kinds


def precheck(question: str) -> PreCheck:
    q = (question or "").strip()
    flags: list[str] = []
    if _OVERRIDE.search(q):
        flags.append("override_attempt")

    # 1. emergency: live-situation language + an emergency term
    if _EMERGENCY_TERMS.search(q) and _LIVE_MARKERS.search(q):
        return PreCheck(State.EMERGENCY, M.EMERGENCY, flags + ["emergency"])

    # 2. privacy: never send identifiers to the model
    kinds = find_pii(q)
    if kinds:
        return PreCheck(State.PRIVACY_BLOCKED, M.PRIVACY_BLOCKED.format(kinds=", ".join(kinds)), flags + ["pii"], kinds)

    # 3. scope
    if _FABRICATE.search(q):
        return PreCheck(State.OUT_OF_SCOPE, M.OUT_OF_SCOPE_FABRICATION, flags + ["fabrication_request"])
    if _PRESCRIBE.search(q):
        return PreCheck(State.OUT_OF_SCOPE, M.OUT_OF_SCOPE, flags + ["prescribing"])
    if _DIAGNOSIS.search(q):
        return PreCheck(State.OUT_OF_SCOPE, M.OUT_OF_SCOPE, flags + ["diagnosis"])
    if _PATIENT_MARKER.search(q) and _DOSE_INTENT.search(q):
        return PreCheck(State.OUT_OF_SCOPE, M.OUT_OF_SCOPE, flags + ["patient_specific_dosing"])

    # 4. too vague to search
    if len(content_terms(q)) < 2:
        return PreCheck(State.NEEDS_CLARIFICATION, M.NEEDS_CLARIFICATION, flags + ["too_vague"])

    return PreCheck(None, "", flags)
