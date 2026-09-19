"""Build the corpus index:  python -m zwtutor.build [--only ID] [--embedder gemini|hash]

1. reads corpus/manifest.json + corpus/pdfs/*.pdf  ->  corpus/chunks.jsonl   (exact text, page + section metadata)
2. embeds the chunks                              ->  corpus/vectors.npy + corpus/index_meta.json
3. prints a report you must read: identity checks, OCR-needed pages, table chunks.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import ingest
from .embed import GeminiEmbedder, HashingEmbedder
from .index import build_index


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="ingest only this source_id")
    ap.add_argument("--embedder", choices=["gemini", "hash"], default="gemini",
                    help="'hash' is a test-only offline embedder, not for real use")
    ap.add_argument("--include-failed", action="store_true", help="index sources even if they failed the identity check / have no text (not recommended)")
    ap.add_argument("--no-embed", action="store_true", help="only write chunks.jsonl")
    a = ap.parse_args(argv)

    try:
        from dotenv import load_dotenv
        load_dotenv(ingest.ROOT / ".env")
    except Exception:  # noqa: BLE001
        pass

    chunks, reports = ingest.ingest_all(only=a.only, include_failed=a.include_failed)
    print(json.dumps(reports, indent=2))
    ingest.REPORT.parent.mkdir(parents=True, exist_ok=True)
    ingest.REPORT.write_text(json.dumps(reports, indent=2), encoding="utf-8")
    if not chunks:
        print("\nNo chunks produced. Run: python scripts/download_corpus.py")
        return 1
    ingest.write_chunks(chunks)
    print(f"\nWrote {len(chunks)} chunks to {ingest.CHUNKS.relative_to(ingest.ROOT)}")
    for r in reports:
        if r.get("excluded_from_index"):
            print(f"EXCLUDED from the index: {r['source_id']} - {r['excluded_from_index']}. Fix the manifest/PDF (or OCR it) and rebuild.")
        elif r.get("error"):
            print(f"MISSING: {r['source_id']} - {r['error']}")

    if a.no_embed:
        return 0
    if a.embedder == "gemini":
        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key or "replace_with" in key:
            print("GEMINI_API_KEY is not set in .env, cannot embed. (Use --embedder hash only for tests.)")
            return 2
        emb = GeminiEmbedder(api_key=key, cache_path=ingest.CORPUS / ".embed_cache.npz")
    else:
        print("WARNING: hashing embedder is for tests only.")
        emb = HashingEmbedder()
    idx = build_index(chunks, emb, ingest.CORPUS)
    print(f"Index built with {idx.meta['embedder']} ({idx.meta['n_chunks']} vectors of {idx.meta['dim']} dims).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
