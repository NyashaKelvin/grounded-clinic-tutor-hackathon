#!/usr/bin/env python
"""Download the corpus PDFs listed in corpus/manifest.json (run this on YOUR computer).

    python scripts/download_corpus.py                 # download everything missing
    python scripts/download_corpus.py --only HIV2022  # one source
    python scripts/download_corpus.py --register      # you saved the PDFs by hand: just record their hashes
    python scripts/download_corpus.py --force         # re-download

It saves each file under corpus/pdfs/, checks that it really is a PDF, and records
its SHA-256 hash and download date in corpus/manifest.lock.json, so every chunk can
later be traced to an exact file. Standard library only.

If a site blocks the script (some serve files only to browsers), open the URL in
your browser, save the file with the name shown below, then run with --register.
The PDFs are NOT to be committed to a public repository unless each licence allows
it (corpus/pdfs/ is git-ignored).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "corpus" / "manifest.json"
LOCK = ROOT / "corpus" / "manifest.lock.json"
PDF_DIR = ROOT / "corpus" / "pdfs"
UA = "Mozilla/5.0 (compatible; ZimbabweNursingTutor-corpus-fetch/1.0; study project)"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.exists() else {}


def is_pdf(path: Path) -> bool:
    with path.open("rb") as f:
        return f.read(5) == b"%PDF-"


def download(url: str, dest: Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/pdf,*/*"})
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(req, timeout=120) as resp, tmp.open("wb") as out:
        final = resp.geturl()
        while True:
            block = resp.read(1 << 20)
            if not block:
                break
            out.write(block)
    if not is_pdf(tmp):
        tmp.unlink(missing_ok=True)
        raise ValueError("the server did not return a PDF (got a web page or an error page)")
    tmp.replace(dest)
    return final


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="source_id to fetch, e.g. HIV2022")
    ap.add_argument("--force", action="store_true", help="download again even if the file exists")
    ap.add_argument("--register", action="store_true", help="do not download; hash PDFs you saved manually")
    args = ap.parse_args()

    sources = json.loads(MANIFEST.read_text(encoding="utf-8"))["sources"]
    if args.only:
        sources = [s for s in sources if s["source_id"] == args.only]
        if not sources:
            print(f"No source with id {args.only!r} in the manifest.")
            return 2
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    lock = load_lock()
    problems = 0

    for s in sources:
        sid, dest = s["source_id"], PDF_DIR / s["pdf_filename"]
        print(f"\n[{sid}] {s['document_title']}")
        if args.register or (dest.exists() and not args.force):
            if not dest.exists():
                print(f"  MISSING. Save the PDF as: {dest}\n  from: {s['document_url']}")
                problems += 1
                continue
            if not is_pdf(dest):
                print(f"  {dest.name} is not a PDF file. Delete it and download again.")
                problems += 1
                continue
            print(f"  using existing file {dest.name}")
            final = lock.get(sid, {}).get("final_url", s["document_url"])
        else:
            try:
                print(f"  downloading {s['document_url']}")
                final = download(s["document_url"], dest)
            except (urllib.error.URLError, ValueError, OSError) as exc:
                print(f"  FAILED: {exc}\n  Open the URL in your browser, save it as {dest} and re-run with --register")
                problems += 1
                continue
        digest = sha256_of(dest)
        prev = lock.get(sid, {}).get("sha256")
        if prev and prev != digest:
            print(f"  NOTE: file differs from the one recorded earlier (hash changed). Re-check edition and year.")
        lock[sid] = {
            "sha256": digest,
            "bytes": dest.stat().st_size,
            "retrieved_on": lock.get(sid, {}).get("retrieved_on") if prev == digest else date.today().isoformat(),
            "final_url": final,
            "file": str(dest.relative_to(ROOT)),
        }
        print(f"  ok  {dest.stat().st_size / 1e6:.1f} MB  sha256={digest[:16]}...")

    LOCK.write_text(json.dumps(lock, indent=2), encoding="utf-8")
    print(f"\nWrote {LOCK.relative_to(ROOT)}. Next: open the first pages of each PDF, correct corpus/manifest.json "
          f"(title, edition, year, licence), then run: python -m zwtutor.build")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
