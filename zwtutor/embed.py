"""Embedders: Gemini (production) and a deterministic hashing embedder (tests / offline only)."""
from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Callable, Optional, Protocol

import numpy as np

GEMINI_EMBED_MODEL = "gemini-embedding-001"
GEMINI_DIM = 768  # docs: 768 / 1536 / 3072 recommended; truncated vectors must be re-normalised by us


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> np.ndarray: ...
    def embed_query(self, text: str) -> np.ndarray: ...


def _unit(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return (m / n).astype(np.float32)


class HashingEmbedder:
    """Character-trigram + word hashing into a fixed-size vector. NOT a real semantic model:
    it exists so the pipeline can be tested without an API key. Never used for real answers."""

    name = "hashing-test-embedder-v1"

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        t = " " + " ".join(text.lower().split()) + " "
        grams = [t[i:i + 3] for i in range(len(t) - 2)] + t.split()
        for g in grams:
            h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
            v[h % self.dim] += 1.0
        return v

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        return _unit(np.stack([self._vec(t) for t in texts])) if texts else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return _unit(self._vec(text)[None, :])[0]


class GeminiEmbedder:
    """gemini-embedding-001 with retrieval task types (only this model supports task_type)."""

    def __init__(self, api_key: Optional[str] = None, client=None, batch: int = 20, cache_path: Optional[Path] = None,
                 sleep: Callable[[float], None] = time.sleep, model: str = GEMINI_EMBED_MODEL, dim: int = GEMINI_DIM, pace: float = 0.65):
        self.model, self.dim, self.batch, self.sleep = model, dim, batch, sleep
        self.pace = pace  # seconds to wait per text embedded
        self.name = f"{model}@{dim}"
        self._client = client
        self._api_key = api_key
        self.cache_path = cache_path
        self._cache: dict[str, np.ndarray] = {}
        if cache_path and cache_path.exists():
            z = np.load(cache_path, allow_pickle=False)
            self._cache = {k: v for k, v in zip(z["keys"].tolist(), z["vecs"])}

    def _c(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    @staticmethod
    def _retry_after(err) -> float:
        """The API says how long to wait ('Please retry in 18.07s'); fall back to a full minute."""
        import re
        m = re.search(r"retry in ([\d.]+)s", getattr(err, "detail", "") or str(err))
        return float(m.group(1)) + 2 if m else 62.0

    def _embed(self, texts: list[str], task: str) -> np.ndarray:
        from google.genai import types
        from tutor import translate_exception  # friendly error mapping already tested

        last = None
        for attempt in range(8):
            try:
                resp = self._c().models.embed_content(
                    model=self.model, contents=texts,
                    config=types.EmbedContentConfig(task_type=task, output_dimensionality=self.dim))
                return _unit(np.array([e.values for e in resp.embeddings], dtype=np.float32))
            except Exception as exc:  # noqa: BLE001
                last = translate_exception(exc)
                if last.kind == "rate_limit" and any(t in (last.detail or "").lower() for t in ("perday", "per day")):
                    raise last  # daily quota: waiting a minute will not help
                if last.kind in ("rate_limit", "unavailable", "network") and attempt < 7:
                    wait = self._retry_after(last) if last.kind == "rate_limit" else min(2 ** attempt * 2, 30)
                    print(f"  waiting {wait:.0f}s ({last.kind}) ...", flush=True)
                    self.sleep(wait)
                    continue
                raise last
        raise last  # pragma: no cover

    def embed_documents(self, texts: list[str]) -> np.ndarray:
        keys = [hashlib.sha1((self.name + "|" + t).encode()).hexdigest() for t in texts]
        todo = [i for i, k in enumerate(keys) if k not in self._cache]
        for b, start in enumerate(range(0, len(todo), self.batch)):
            idx = todo[start:start + self.batch]
            vecs = self._embed([texts[i] for i in idx], "RETRIEVAL_DOCUMENT")
            for i, v in zip(idx, vecs):
                self._cache[keys[i]] = v
            if self.cache_path:
                self._save()  # progress survives a crash or a quota stop: just re-run the build
            print(f"  embedded {min(start + self.batch, len(todo))}/{len(todo)}", flush=True)
            self.sleep(self.pace * len(idx))  # free tier counts each text: about 100 per minute
        if self.cache_path and todo:
            self._save()
        return np.stack([self._cache[k] for k in keys]) if keys else np.zeros((0, self.dim), np.float32)

    def embed_query(self, text: str) -> np.ndarray:
        return self._embed([text], "RETRIEVAL_QUERY")[0]

    def _save(self) -> None:
        keys = np.array(list(self._cache.keys()))
        vecs = np.stack(list(self._cache.values())) if self._cache else np.zeros((0, self.dim), np.float32)
        np.savez_compressed(self.cache_path, keys=keys, vecs=vecs)
