"""Synthetic test fixtures. The 'medical' content below is INVENTED nonsense for testing
the pipeline (fake drug names, fake numbers). It must never be used as, or mixed into, the real corpus."""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf

TITLE = "SYNTHETIC TEST GUIDELINE for the Imaginary Ward"
INTRO = ("This synthetic document exists only to test software. It describes an imaginary ward where nurses "
         "practise with invented drugs. None of the statements are real clinical guidance. ") * 3
SEC1 = ("Zorbex is an invented drug. For adults on the imaginary ward give Zorbex 5 mg twice daily for 7 days. "
        "Monitor the imaginary pulse every 4 hours. Stop Zorbex if the imaginary temperature exceeds 38.5 degrees. "
        "Nurses should document each dose in the ward book. ") * 2
SEC2 = ("Quillon is a second invented drug. For children give Quillon 2.5 mg per kg once daily for 3 days. "
        "Store Quillon at room temperature away from moisture. Report any imaginary rash to the supervisor. ") * 2
SEC3 = ("The Blorp assessment has five steps: Look, Listen, Touch, Ask, Record. Complete all five steps before "
        "escalating to the imaginary doctor. ") * 2


def make_pdf(path: Path, scanned_page: bool = False) -> dict:
    doc = pymupdf.open()

    def new_page(header=True, footer_no=None):
        p = doc.new_page(width=595, height=842)
        if header:
            p.insert_text((60, 30), "Imaginary Ministry of Testing", fontsize=8, fontname="helv")
        if footer_no is not None:
            p.insert_text((290, 820), str(footer_no), fontsize=9, fontname="helv")
        return p

    p1 = new_page(footer_no=1)
    p1.insert_text((60, 100), TITLE, fontsize=20, fontname="hebo")
    p1.insert_textbox(pymupdf.Rect(60, 130, 540, 400), INTRO, fontsize=10, fontname="helv")

    p2 = new_page(footer_no=2)
    p2.insert_text((60, 90), "1 Adult dosing", fontsize=16, fontname="hebo")
    p2.insert_textbox(pymupdf.Rect(60, 110, 540, 330), SEC1, fontsize=10, fontname="helv")
    p2.insert_text((60, 360), "2 Child dosing", fontsize=16, fontname="hebo")
    p2.insert_textbox(pymupdf.Rect(60, 380, 540, 600), SEC2, fontsize=10, fontname="helv")

    p3 = new_page(footer_no=3)
    p3.insert_text((60, 90), "3 Assessment", fontsize=16, fontname="hebo")
    p3.insert_textbox(pymupdf.Rect(60, 110, 540, 300), SEC3, fontsize=10, fontname="helv")

    if scanned_page:
        p4 = new_page(header=False)
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
        pix.set_rect(pix.irect, (200, 200, 200))
        p4.insert_image(pymupdf.Rect(60, 100, 300, 300), pixmap=pix)
    doc.save(path)
    doc.close()
    return {"title": TITLE, "pages": 4 if scanned_page else 3}


def source_entry(pdf_name="SYNTH.pdf") -> dict:
    return {
        "source_id": "SYNTH", "institution": "Imaginary Ministry of Testing", "document_title": TITLE,
        "edition": "1st test edition", "publication_year": "2099", "document_url": "https://example.invalid/synth.pdf",
        "licence_or_reuse_status": "synthetic test fixture", "clinical_topic": "testing",
        "currency_status": "verified_current", "currency_note": "", "pdf_filename": pdf_name, "min_pages": 3,
        "title_keywords": ["synthetic", "imaginary ward"],
    }


def write_manifest(dirpath: Path) -> tuple[Path, Path]:
    dirpath.mkdir(parents=True, exist_ok=True)
    pdfs = dirpath / "pdfs"
    pdfs.mkdir(exist_ok=True)
    make_pdf(pdfs / "SYNTH.pdf")
    man = dirpath / "manifest.json"
    man.write_text(json.dumps({"sources": [source_entry()]}), encoding="utf-8")
    return man, pdfs
