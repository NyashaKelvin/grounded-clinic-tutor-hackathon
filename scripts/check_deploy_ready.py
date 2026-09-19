"""Is this repository ready to deploy WITHOUT rebuilding the index?   python scripts/check_deploy_ready.py

Checks that the built index is present and consistent, that no secrets or PDFs would be uploaded, and lists the
licence status of every source whose text is inside the committed index.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OK, WARN, FAIL = "OK  ", "WARN", "FAIL"
NEED = {"streamlit", "google-genai", "python-dotenv", "numpy", "pymupdf"}


def _git(root: Path, *args) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, timeout=30)
        return r.stdout if r.returncode == 0 else None
    except Exception:  # noqa: BLE001
        return None


def check(root: Path = ROOT) -> list[tuple[str, str]]:
    from zwtutor import ingest
    from zwtutor.index import load_index

    out: list[tuple[str, str]] = []
    c = root / "corpus"
    need = ["chunks.jsonl", "vectors.npy", "index_meta.json", "manifest.json"]
    missing = [n for n in need if not (c / n).exists()]
    if missing:
        return [(FAIL, f"missing in corpus/: {missing}. Run: python -m zwtutor.build")]
    try:
        chunks = ingest.load_chunks(c / "chunks.jsonl")
        idx = load_index(c, chunks)
        out.append((OK, f"index loads: {len(chunks)} passages, {idx.vectors.shape[1]} dims, embedder {idx.meta['embedder']}"))
        if idx.meta["embedder"].startswith("hashing"):
            out.append((FAIL, "index was built with the TEST-ONLY hashing embedder. Rebuild with your Gemini key."))
    except Exception as exc:  # noqa: BLE001
        return [(FAIL, f"index is not usable: {exc}")]

    for n in ("chunks.jsonl", "vectors.npy"):
        mb = (c / n).stat().st_size / 1e6
        out.append((OK if mb < 50 else FAIL, f"{n}: {mb:.1f} MB (GitHub rejects files over 100 MB)"))

    reqs = {l.strip().lower().split("=")[0].split("<")[0].split(">")[0].split("[")[0]
            for l in (root / "requirements.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
    miss = NEED - reqs
    out.append((FAIL, f"requirements.txt lacks: {sorted(miss)}") if miss else (OK, "requirements.txt has every runtime dependency"))

    tracked = _git(root, "ls-files")
    if tracked is None:
        out.append((WARN, "not a git repository (or git not installed): cannot check what would be uploaded"))
    else:
        files = tracked.splitlines()
        bad = [f for f in files if f.lower().endswith(".pdf") or f.split("/")[-1] == ".env" or f.endswith("secrets.toml")]
        out.append((FAIL, f"tracked files that must not be uploaded: {bad}") if bad else (OK, "no PDFs, .env or secrets are tracked"))
        for n in ("chunks.jsonl", "vectors.npy", "index_meta.json"):
            if f"corpus/{n}" not in files:
                out.append((FAIL, f"corpus/{n} is not committed: the deployed app would have to rebuild. `git add corpus/{n}`"))
        if (_git(root, "status", "--porcelain", "corpus/chunks.jsonl", "corpus/vectors.npy", "corpus/index_meta.json") or "").strip():
            out.append((WARN, "the index files have uncommitted changes: commit them so the deployed copy matches"))

    seen = {}
    for ch in chunks:
        seen.setdefault(ch.source_id, ch)
    for sid, ch in seen.items():
        out.append((WARN, f"{sid}: reuse status = '{ch.licence_or_reuse_status or 'not stated'}'. Its text is inside chunks.jsonl; "
                          "confirm you may publish it, or keep the repository private."))
    return out


def main() -> int:
    res = check()
    for st, msg in res:
        print(f"[{st}] {msg}")
    fails = sum(1 for s, _ in res if s == FAIL)
    print("\nNOT ready." if fails else "\nReady to deploy (read the WARN lines).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
