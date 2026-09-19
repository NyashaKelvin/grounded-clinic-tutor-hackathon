"""Hybrid retrieval: embedding cosine + BM25 keywords, with a per-document cap and term coverage."""
from __future__ import annotations

import numpy as np

from .index import Index
from .models import Evidence, Hit
from .textutil import content_terms


class Retriever:
    def __init__(self, index: Index, embedder, k: int = 6, per_source_cap: int = 4, w_sem: float = 0.65):
        self.index, self.embedder = index, embedder
        self.k, self.cap, self.w_sem = k, per_source_cap, w_sem

    def search(self, query: str) -> Evidence:
        terms = content_terms(query)
        n = len(self.index.chunks)
        if n == 0:
            return Evidence([], 0.0, 0.0, terms)
        q = self.embedder.embed_query(query)
        sem = self.index.vectors @ q  # both unit-length -> cosine
        kw = self.index.bm25.scores(terms)
        kw_n = kw / kw.max() if kw.max() > 0 else kw
        fused = self.w_sem * sem + (1 - self.w_sem) * kw_n

        hits: list[Hit] = []
        per_source: dict[str, int] = {}
        for i in np.argsort(-fused):
            c = self.index.chunks[i]
            if per_source.get(c.source_id, 0) >= self.cap:
                continue
            per_source[c.source_id] = per_source.get(c.source_id, 0) + 1
            present = self.index.term_sets[i]
            cov = (sum(1 for t in terms if t in present) / len(terms)) if terms else 0.0
            hits.append(Hit(c, float(sem[i]), float(kw_n[i]), float(fused[i]), float(cov)))
            if len(hits) >= self.k:
                break
        best = hits[0] if hits else None
        return Evidence(hits, best.sem if best else 0.0, best.coverage if best else 0.0, terms)
