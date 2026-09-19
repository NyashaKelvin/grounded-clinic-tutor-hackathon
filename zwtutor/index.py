"""Vector + keyword index over the chunks."""
from __future__ import annotations

import hashlib
import json
import math
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .models import Chunk
from .textutil import content_terms, stem, tokens


def chunks_fingerprint(chunks: list[Chunk]) -> str:
    h = hashlib.sha256()
    for c in chunks:
        h.update(c.chunk_id.encode())
        h.update(hashlib.sha256(c.source_text.encode()).digest())
    return h.hexdigest()


def embed_text(c: Chunk) -> str:
    """What is embedded: source + section context help retrieval; the stored source_text is unchanged."""
    return f"{c.document_title} > {c.section}\n{c.source_text}"


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(d) for d in docs]
        self.len = np.array([len(d) for d in docs], dtype=np.float32)
        self.avg = float(self.len.mean()) if len(docs) else 0.0
        df: Counter = Counter()
        for d in self.tf:
            df.update(d.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def scores(self, terms: list[str]) -> np.ndarray:
        out = np.zeros(len(self.tf), dtype=np.float32)
        for t in terms:
            idf = self.idf.get(t)
            if not idf:
                continue
            for i, tf in enumerate(self.tf):
                f = tf.get(t, 0)
                if f:
                    out[i] += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[i] / (self.avg or 1)))
        return out


def _doc_terms(c: Chunk) -> list[str]:
    return [t if t[0].isdigit() else stem(t) for t in tokens(c.section + " " + c.source_text)]


@dataclass
class Index:
    chunks: list[Chunk]
    vectors: np.ndarray
    meta: dict = field(default_factory=dict)
    bm25: Optional[BM25] = None
    by_id: dict = field(default_factory=dict)
    term_sets: list = field(default_factory=list)

    def __post_init__(self):
        self.by_id = {c.chunk_id: c for c in self.chunks}
        docs = [_doc_terms(c) for c in self.chunks]
        self.term_sets = [set(d) for d in docs]
        self.bm25 = BM25(docs)

    def topics(self) -> list[dict]:
        """Deterministic topic tree from headings: [{source_id, title, sections: {top: [sub,...]}}]."""
        tree: dict = {}
        for c in self.chunks:
            parts = [p for p in c.section.split(" > ") if p]
            top, sub = (parts[1] if len(parts) > 1 else (parts[0] if parts else "")), (parts[2] if len(parts) > 2 else "")
            d = tree.setdefault(c.source_id, {"source_id": c.source_id, "title": c.document_title, "sections": {}})
            if top:
                d["sections"].setdefault(top, set())
                if sub:
                    d["sections"][top].add(sub)
        return [{"source_id": v["source_id"], "title": v["title"],
                 "sections": {k: sorted(s) for k, s in v["sections"].items()}} for v in tree.values()]


def build_index(chunks: list[Chunk], embedder, out_dir: Path) -> Index:
    out_dir.mkdir(parents=True, exist_ok=True)
    vecs = embedder.embed_documents([embed_text(c) for c in chunks])
    np.save(out_dir / "vectors.npy", vecs)
    meta = {"embedder": embedder.name, "dim": int(vecs.shape[1]) if len(vecs) else 0, "n_chunks": len(chunks),
            "chunks_sha256": chunks_fingerprint(chunks), "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    (out_dir / "index_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return Index(chunks, vecs, meta)


def load_index(out_dir: Path, chunks: list[Chunk]) -> Index:
    meta = json.loads((out_dir / "index_meta.json").read_text(encoding="utf-8"))
    if meta["chunks_sha256"] != chunks_fingerprint(chunks):
        raise ValueError("The vector index does not match chunks.jsonl (stale). Re-run: python -m zwtutor.build")
    vecs = np.load(out_dir / "vectors.npy")
    if len(vecs) != len(chunks):
        raise ValueError("Vector count differs from chunk count. Re-run: python -m zwtutor.build")
    return Index(chunks, vecs, meta)


__all__ = ["Index", "BM25", "build_index", "load_index", "embed_text", "chunks_fingerprint", "content_terms"]
