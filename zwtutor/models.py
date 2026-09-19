"""Data models shared across the pipeline."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from typing import Any, Optional


class State(str, Enum):
    """Every outcome the tutor can return. Chosen by code, never by the model's judgment."""
    GROUNDED = "GROUNDED"
    NOT_IN_CORPUS = "NOT_IN_CORPUS"
    CONFLICTING_SOURCES = "CONFLICTING_SOURCES"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    CANNOT_VERIFY = "CANNOT_VERIFY"
    EMERGENCY = "EMERGENCY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    PRIVACY_BLOCKED = "PRIVACY_BLOCKED"


@dataclass(frozen=True)
class Chunk:
    source_id: str
    institution: str
    document_title: str
    edition: str
    publication_year: str
    section: str
    page_number: Optional[str]  # printed page number if detected
    pdf_page: int  # 1-based page index in the PDF file
    document_url: str
    licence_or_reuse_status: str
    clinical_topic: str
    chunk_id: str
    source_text: str  # exact extracted text, never edited
    extraction_method: str = "text"
    file_sha256: str = ""
    currency_status: str = "requires_verification"
    currency_note: str = ""
    retrieved_on: str = ""
    has_table: bool = False
    word_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chunk":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})

    def page_label(self) -> str:
        if self.page_number:
            return f"{self.page_number} (PDF page {self.pdf_page})"
        return f"PDF page {self.pdf_page}"


@dataclass
class Hit:
    chunk: Chunk
    sem: float  # cosine similarity to the question
    bm25: float  # normalised keyword score 0..1
    fused: float
    coverage: float  # share of the question's key terms present in this chunk


@dataclass
class Evidence:
    hits: list[Hit]
    top_sem: float
    top_cov: float
    query_terms: list[str]


@dataclass
class CitationView:
    chunk: Chunk
    quote: str
    verified: bool
    claim: str = ""


@dataclass
class TutorResult:
    state: State
    mode: str
    message: str = ""  # refusal / status text shown to the learner
    answer: str = ""
    points: list[dict] = field(default_factory=list)  # {"text", "citations": [CitationView], "verified": bool}
    memory_aid: Optional[dict] = None  # {"text", "expands_to", "expansions"}
    quiz: list[dict] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    evidence: list[Hit] = field(default_factory=list)  # closest passages (for source mode / refusals)
    flags: list[str] = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    conflict: Optional[dict] = None
    gate: dict = field(default_factory=dict)
    model_used: str = ""
    generated: bool = False  # True only if the answering model was called
