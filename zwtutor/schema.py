"""Teaching modes, and the JSON schema the model must follow (chunk_id restricted to this request's chunks)."""
from __future__ import annotations

MODES = {
    "explain":    ("Explain", "Explain the topic clearly in a few cited points."),
    "teach":      ("Teach me", "Teach step by step: 3-6 short points from basic to detail, each cited."),
    "simplify":   ("Simplify", "Explain in plain, simple words. Do not add any fact the passages lack."),
    "mnemonic":   ("Memory aid", "Give the cited teaching points, then a memory aid built ONLY from those points."),
    "quiz":       ("Quiz me", "Write 3 short-answer questions. Every answer must be stated in the passages."),
    "exam":       ("Exam style", "Write 3 multiple-choice questions (4 options). The correct answer must be in the passages."),
    "flashcards": ("Flashcards", "Write 4-6 flashcards; the back of each must be stated in the passages."),
    "compare":    ("Compare", "Compare the items asked about, point by point, only where the passages support it."),
    "case":       ("Case study", "Write a short teaching case scenario, then cited points on what the sources say. No patient-specific dosing."),
    "teachback":  ("Teach-back", "Ask the learner to explain it back; give 3 cited checklist points to mark their answer against."),
    "source":     ("Show sources", "No AI writing: show the closest source passages only."),
}
GENERATIVE_MODES = [m for m in MODES if m != "source"]


def _cite(ids: list[str]) -> dict:
    return {"type": "array", "minItems": 1, "maxItems": 3, "items": {
        "type": "object", "properties": {
            "chunk_id": {"type": "string", "enum": ids},
            "quote": {"type": "string", "description": "EXACT contiguous words copied from that chunk, at least 5 words"}},
        "required": ["chunk_id", "quote"]}}


def build_schema(mode: str, chunk_ids: list[str]) -> dict:
    cite = _cite(chunk_ids)
    point = {"type": "object", "properties": {"text": {"type": "string"}, "citations": cite}, "required": ["text", "citations"]}
    props: dict = {
        "cannot_answer": {"type": "boolean", "description": "true if the passages do not actually answer the question"},
        "summary": {"type": "string", "description": "One or two sentences. No number that is not in the passages."},
        "points": {"type": "array", "items": point, "maxItems": 8},
        "conflict": {"type": "object", "properties": {
            "exists": {"type": "boolean"}, "description": {"type": "string"}}, "required": ["exists", "description"]},
        "limitations": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
    }
    if mode == "mnemonic":
        props["memory_aid"] = {"type": "object", "properties": {
            "text": {"type": "string", "description": "letters only, e.g. LLT"},
            "letters": {"type": "array", "items": {"type": "object", "properties": {
                "stands_for": {"type": "string", "description": "a word taken from the point it is tied to"},
                "point_index": {"type": "integer", "description": "0-based index into points"}},
                "required": ["stands_for", "point_index"]}}}, "required": ["text", "letters"]}
    if mode in ("quiz", "exam"):
        q = {"question": {"type": "string"}, "answer": {"type": "string"}, "explanation": {"type": "string"},
             "citations": cite}
        req = ["question", "answer", "citations"]
        if mode == "exam":
            q["options"] = {"type": "array", "items": {"type": "string"}, "minItems": 4, "maxItems": 4}
            req.append("options")
        props["quiz"] = {"type": "array", "maxItems": 4, "items": {"type": "object", "properties": q, "required": req}}
    if mode == "flashcards":
        props["cards"] = {"type": "array", "maxItems": 6, "items": {"type": "object", "properties": {
            "front": {"type": "string"}, "back": {"type": "string"}, "citations": cite}, "required": ["front", "back", "citations"]}}
    if mode == "case":
        props["scenario"] = {"type": "string", "description": "invented teaching scenario with NO doses, numbers or facts"}
    return {"type": "object", "properties": props, "required": ["cannot_answer", "points", "conflict"]}
