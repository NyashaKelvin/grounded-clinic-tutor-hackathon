"""Loads the built corpus and wires a Tutor. Kept out of app.py so it can be tested."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from . import ingest
from .embed import GeminiEmbedder, HashingEmbedder
from .gate import load_config
from . import generate
from .generate import GeminiGenerator
from .index import load_index
from .pipeline import Tutor


class SetupError(Exception):
    """Something the user must do first. The message says exactly what."""


@dataclass
class Loaded:
    tutor: Tutor
    index: object
    corpus_ok: bool


def get_key() -> str:
    k = os.getenv("GEMINI_API_KEY", "").strip()
    return "" if (not k or "replace_with" in k) else k


def load_tutor(api_key: str, strict: bool = True) -> Tutor:
    if not ingest.CHUNKS.exists():
        raise SetupError("The corpus has not been built yet. Run:  python scripts/download_corpus.py  then  python -m zwtutor.build")
    chunks = ingest.load_chunks(ingest.CHUNKS)
    try:
        index = load_index(ingest.CORPUS, chunks)
    except FileNotFoundError:
        raise SetupError("The vector index is missing. Run:  python -m zwtutor.build")
    except ValueError as exc:
        raise SetupError(str(exc))
    name = index.meta.get("embedder", "")
    if name.startswith("hashing"):
        if os.getenv("ALLOW_TEST_EMBEDDER") != "1":
            raise SetupError("The index was built with the test-only hashing embedder. Rebuild with your Gemini key: python -m zwtutor.build")
        emb = HashingEmbedder()
    else:
        if not api_key:
            raise SetupError("Add your Gemini API key (sidebar or .env) to search the sources.")
        model, _, dim = name.partition("@")
        emb = GeminiEmbedder(api_key=api_key, model=model, dim=int(dim or 768))
    return Tutor(index, emb, GeminiGenerator(api_key=api_key), load_config(), strict=strict)
