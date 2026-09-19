"""PDF -> chunks with page, section and source metadata (PyMuPDF).

Every chunk lies inside ONE PDF page, so it can be traced back to that page. Headings are
detected from font size / boldness. Text is stored exactly as extracted.

KNOWN LIMITS: two-column layouts may interleave; tables may extract with columns run
together (chunks that overlap a table are flagged `has_table`); scanned pages are counted
and reported but not OCR'd here (OCR is out of scope unless a PDF turns out to be scanned).
"""
from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Optional

import pymupdf

from .models import Chunk

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
MANIFEST = CORPUS / "manifest.json"
LOCK = CORPUS / "manifest.lock.json"
PDF_DIR = CORPUS / "pdfs"
CHUNKS = CORPUS / "chunks.jsonl"
REPORT = CORPUS / "ingest_report.json"

TARGET_WORDS, MAX_WORDS, MIN_WORDS, MIN_KEEP_WORDS = 220, 320, 40, 6
_SENT = re.compile(r"(?<=[.!?])\s+")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(path: Path = MANIFEST) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["sources"]


def load_lock(path: Path = LOCK) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# ------------------------------------------------------------------ page reading
def _page_lines(page):
    """Yield (bbox, [(text, size, bold), ...]) for each text block, in extraction order."""
    d = page.get_text("dict")
    for block in d["blocks"]:
        if block.get("type") != 0:
            continue
        lines = []
        for line in block["lines"]:
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            text = "".join(s["text"] for s in line["spans"]).strip()
            size = max(s["size"] for s in spans)
            bold = all(bool(s["flags"] & 16) or "bold" in s["font"].lower() for s in spans)
            lines.append((text, round(size, 1), bold))
        if lines:
            yield tuple(block["bbox"]), lines


def _body_size(doc) -> float:
    weights: Counter = Counter()
    for page in doc:
        for _bbox, lines in _page_lines(page):
            for text, size, _b in lines:
                weights[size] += len(text)
    if not weights:
        return 10.0
    total, acc = sum(weights.values()), 0
    for size, w in sorted(weights.items()):
        acc += w
        if acc >= total / 2:
            return size
    return 10.0


def _running_lines(doc, zone: float = 0.07) -> set[str]:
    """Header/footer text repeated on many pages (dropped from chunks)."""
    counts: Counter = Counter()
    n = max(len(doc), 1)
    for page in doc:
        h = page.rect.height
        seen = set()
        for bbox, lines in _page_lines(page):
            if bbox[3] < h * zone or bbox[1] > h * (1 - zone):
                for text, _s, _b in lines:
                    key = re.sub(r"\d+", "#", text.lower())
                    seen.add(key)
        counts.update(seen)
    return {k for k, c in counts.items() if c >= max(3, 0.3 * n) and len(k) > 2}


def _printed_page(page, running: set[str]) -> Optional[str]:
    h = page.rect.height
    for bbox, lines in _page_lines(page):
        if bbox[3] < h * 0.09 or bbox[1] > h * 0.91:
            for text, _s, _b in lines:
                m = re.fullmatch(r"(?:page\s*)?(\d{1,4})", text.strip(), re.I)
                if m:
                    return m.group(1)
    return None


def _table_boxes(page) -> list:
    try:
        return [pymupdf.Rect(t.bbox) for t in page.find_tables().tables]
    except Exception:  # noqa: BLE001 - table finding is best-effort
        return []


def _looks_tabular(text: str) -> bool:
    lines = [l for l in text.splitlines() if l.strip()]
    if len(lines) < 4:
        return False
    numeric = sum(1 for l in lines if len(re.findall(r"\d", l)) >= 2 and len(l.split()) <= 6)
    return numeric / len(lines) >= 0.5


def _is_heading(text: str, size: float, bold: bool, body: float, block_lines: int, block_all_bold: bool) -> bool:
    t = text.strip()
    if not t or len(t) > 120 or re.fullmatch(r"[\d\W]+", t):
        return False
    if size >= body * 1.15:
        return True
    return bool(block_all_bold and block_lines <= 2 and len(t) <= 90 and size >= body * 0.95 and not t.endswith((".", ",", ";")))


def _split_long(text: str) -> list[str]:
    words = text.split()
    if len(words) <= MAX_WORDS:
        return [text]
    out, cur = [], []
    for sent in _SENT.split(text):
        if cur and len(" ".join(cur + [sent]).split()) > MAX_WORDS:
            out.append(" ".join(cur))
            cur = []
        cur.append(sent)
    if cur:
        out.append(" ".join(cur))
    return out


# ------------------------------------------------------------------ main entry
def ingest_pdf(pdf_path: Path, source: dict, lock_entry: Optional[dict] = None) -> tuple[list[Chunk], dict]:
    """Return (chunks, report) for one PDF."""
    lock_entry = lock_entry or {}
    sha = lock_entry.get("sha256") or sha256_file(pdf_path)
    doc = pymupdf.open(pdf_path)
    body = _body_size(doc)
    running = _running_lines(doc)
    report = {
        "source_id": source["source_id"], "pdf": str(pdf_path.name), "pages": len(doc), "chunks": 0, "words": 0,
        "pages_needing_ocr": [], "table_chunks": 0, "warnings": [], "sha256": sha,
    }

    # identity check: is this the document the manifest says it is?
    head = " ".join(doc[i].get_text().lower() for i in range(min(3, len(doc))))
    missing = [k for k in source.get("title_keywords", []) if k.lower() not in head]
    report["identity_check"] = "pass" if not missing else f"FAIL: first pages lack {missing}"
    if missing:
        report["warnings"].append(f"First pages do not contain {missing}: is this the right file? Check title/edition/year.")
    if len(doc) < source.get("min_pages", 1):
        report["warnings"].append(f"Only {len(doc)} pages (expected at least {source['min_pages']}).")

    # heading levels from font sizes
    sizes = Counter()
    for page in doc:
        for _b, lines in _page_lines(page):
            n, all_bold = len(lines), all(b for _t, _s, b in lines)
            for t, s, b in lines:
                if _is_heading(t, s, b, body, n, all_bold):
                    sizes[s] += 1
    level_of = {s: i for i, s in enumerate(sorted(sizes, reverse=True)[:4])}

    section: list[str] = []
    chunks: list[Chunk] = []

    for pno, page in enumerate(doc, start=1):
        page_text = page.get_text()
        if len(page_text.strip()) < 25 and page.get_images():
            report["pages_needing_ocr"].append(pno)
            continue
        printed = _printed_page(page, running)
        tables = _table_boxes(page)
        h = page.rect.height

        cur: list[str] = []
        cur_words = 0
        cur_table = False
        cur_section = " > ".join(section)
        page_chunks: list[dict] = []

        def flush():
            nonlocal cur, cur_words, cur_table
            if cur:
                page_chunks.append({"section": cur_section, "text": "\n".join(cur).strip(), "table": cur_table})
            cur, cur_words, cur_table = [], 0, False

        for bbox, lines in _page_lines(page):
            if bbox[3] < h * 0.07 or bbox[1] > h * 0.93:
                if all(re.sub(r"\d+", "#", t.lower()) in running or re.fullmatch(r"(?:page\s*)?\d{1,4}", t.strip(), re.I) for t, _s, _b in lines):
                    continue
            in_table = any(pymupdf.Rect(bbox).intersects(tb) for tb in tables)
            n, all_bold = len(lines), all(b for _t, _s, b in lines)
            para: list[str] = []

            def emit_para():
                nonlocal cur_words, cur_table, cur_section
                if not para:
                    return
                text = " ".join(para) if not in_table else "\n".join(para)
                for piece in _split_long(text):
                    w = len(piece.split())
                    if cur_words + w > MAX_WORDS and cur_words >= MIN_WORDS:
                        flush()
                        cur_section = " > ".join(section)
                    cur.append(piece)
                    cur_words += w
                    cur_table = cur_table or in_table or _looks_tabular(piece)
                    if cur_words >= TARGET_WORDS:
                        flush()
                        cur_section = " > ".join(section)
                para.clear()

            for text, size, bold in lines:
                if _is_heading(text, size, bold, body, n, all_bold) and size in level_of:
                    emit_para()
                    flush()
                    lvl = level_of[size]
                    del section[lvl:]
                    section.append(text.strip())
                    cur_section = " > ".join(section)
                    cur.append(text.strip())
                    cur_words += len(text.split())
                else:
                    para.append(text)
            emit_para()
        flush()

        # merge a tiny trailing chunk into the previous one (same section)
        merged: list[dict] = []
        for c in page_chunks:
            wc = len(c["text"].split())
            if merged and wc < MIN_WORDS and merged[-1]["section"] == c["section"]:
                merged[-1]["text"] += "\n" + c["text"]
                merged[-1]["table"] = merged[-1]["table"] or c["table"]
            else:
                merged.append(c)
        seq = 0
        for c in merged:
            wc = len(c["text"].split())
            if wc < MIN_KEEP_WORDS and not c["table"]:
                continue
            seq += 1
            chunks.append(Chunk(
                source_id=source["source_id"], institution=source["institution"], document_title=source["document_title"],
                edition=source["edition"], publication_year=str(source["publication_year"]), section=c["section"],
                page_number=printed, pdf_page=pno, document_url=source["document_url"],
                licence_or_reuse_status=source["licence_or_reuse_status"], clinical_topic=source["clinical_topic"],
                chunk_id=f"{source['source_id']}:p{pno}:{seq}", source_text=c["text"], extraction_method="text",
                file_sha256=sha, currency_status=source.get("currency_status", "requires_verification"),
                currency_note=source.get("currency_note", ""), retrieved_on=lock_entry.get("retrieved_on", ""),
                has_table=bool(c["table"]), word_count=wc,
            ))

    report["chunks"] = len(chunks)
    report["words"] = sum(c.word_count for c in chunks)
    report["table_chunks"] = sum(c.has_table for c in chunks)
    if report["pages_needing_ocr"]:
        report["warnings"].append(f"{len(report['pages_needing_ocr'])} page(s) have no text layer and were skipped (need OCR).")
    doc.close()
    return chunks, report


def ingest_all(only: Optional[str] = None, manifest: Path = MANIFEST, pdf_dir: Path = PDF_DIR, lock: Path = LOCK,
               include_failed: bool = False):
    sources = load_manifest(manifest)
    locks = load_lock(lock)
    all_chunks: list[Chunk] = []
    reports = []
    for s in sources:
        if only and s["source_id"] != only:
            continue
        pdf = pdf_dir / s["pdf_filename"]
        if not pdf.exists():
            reports.append({"source_id": s["source_id"], "error": f"missing file {pdf.name}: run scripts/download_corpus.py"})
            continue
        chunks, rep = ingest_pdf(pdf, s, locks.get(s["source_id"]))
        # A source that failed the identity check, or is mostly scanned images with no text layer,
        # is EXCLUDED from the index: we will not answer from a file we could not read or identify.
        pages = max(1, rep.get("pages", 1))
        reason = ""
        if str(rep.get("identity_check", "pass")) != "pass":
            reason = "identity check failed"
        elif rep.get("words", 0) / pages < 40:
            reason = f"almost no text ({rep.get('words', 0)} words on {pages} pages: a scanned document that needs OCR)"
        if reason and not include_failed:
            rep["excluded_from_index"] = reason
            reports.append(rep)
            continue
        all_chunks += chunks
        reports.append(rep)
    return all_chunks, reports


def write_chunks(chunks: list[Chunk], path: Path = CHUNKS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")


def load_chunks(path: Path = CHUNKS) -> list[Chunk]:
    # NOT str.splitlines(): it also splits on U+2028, U+0085 and similar characters that PDF text contains
    # and json.dumps(ensure_ascii=False) leaves unescaped, which would cut a record in half.
    text = path.read_text(encoding="utf-8")
    return [Chunk.from_dict(json.loads(l)) for l in text.split("\n") if l.strip()]
