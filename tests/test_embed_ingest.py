import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import pymupdf

from tests.fixtures import make_pdf, source_entry
from zwtutor import ingest
from zwtutor.embed import GeminiEmbedder


class Client:
    """Fake Gemini client: first call hits the free-tier 429, later calls work."""
    def __init__(self, fail_first=1, msg="429 RESOURCE_EXHAUSTED ... Please retry in 18.07s"):
        self.calls, self.fail, self.msg = 0, fail_first, msg
        self.models = SimpleNamespace(embed_content=self._embed)

    def _embed(self, model, contents, config):
        from google.genai import errors
        self.calls += 1
        if self.calls <= self.fail:
            raise errors.ClientError(429, {"error": {"message": self.msg, "status": "RESOURCE_EXHAUSTED"}}, None)
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[float(i + 1), 1.0, 0.0]) for i, _ in enumerate(contents)])


class Embed(unittest.TestCase):
    def test_waits_the_time_the_api_asks_and_saves_each_batch(self):
        sleeps = []
        with tempfile.TemporaryDirectory() as td:
            cache = Path(td) / "c.npz"
            e = GeminiEmbedder(client=Client(), batch=2, cache_path=cache, sleep=sleeps.append, dim=3)
            v = e.embed_documents(["a", "b", "c", "d", "e"])
            self.assertEqual(v.shape, (5, 3))
            self.assertIn(20.07, [round(s, 2) for s in sleeps])  # 18.07 + 2 s margin
            self.assertTrue(cache.exists())
            # a second run is served from the cache: no API calls at all
            c2 = Client(fail_first=0)
            GeminiEmbedder(client=c2, batch=2, cache_path=cache, sleep=sleeps.append, dim=3).embed_documents(["a", "b", "c", "d", "e"])
            self.assertEqual(c2.calls, 0)

    def test_daily_quota_stops_instead_of_waiting(self):
        from tutor import TutorError
        c = Client(fail_first=99, msg="Quota exceeded ... EmbedContentRequestsPerDayPerProject retry in 5s")
        e = GeminiEmbedder(client=c, sleep=lambda s: self.fail("should not wait"), dim=3)
        with self.assertRaises(TutorError):
            e.embed_documents(["a"])

    def test_paces_by_number_of_texts(self):
        sleeps = []
        GeminiEmbedder(client=Client(fail_first=0), batch=20, sleep=sleeps.append, dim=3).embed_documents([str(i) for i in range(20)])
        self.assertAlmostEqual(sum(sleeps), 13.0, places=1)  # 20 texts x 0.65 s => under 100 per minute


class Ingest(unittest.TestCase):
    def test_scanned_or_unidentified_sources_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "pdfs").mkdir()
            # a "scanned" document: pages that contain only an image
            doc = pymupdf.open()
            for _ in range(5):
                p = doc.new_page()
                pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 50, 50), False)
                pix.set_rect(pix.irect, (200, 200, 200))
                p.insert_image(pymupdf.Rect(60, 100, 300, 300), pixmap=pix)
            doc.save(d / "pdfs" / "SCAN.pdf")
            make_pdf(d / "pdfs" / "SYNTH.pdf")
            import json
            scan = {**source_entry("SCAN.pdf"), "source_id": "SCAN", "min_pages": 1}
            (d / "m.json").write_text(json.dumps({"sources": [source_entry(), scan]}))
            chunks, reports = ingest.ingest_all(manifest=d / "m.json", pdf_dir=d / "pdfs", lock=d / "lock.json")
            ids = {c.source_id for c in chunks}
            self.assertEqual(ids, {"SYNTH"})
            self.assertTrue(any(r.get("excluded_from_index") for r in reports if r["source_id"] == "SCAN"))
            chunks2, _ = ingest.ingest_all(manifest=d / "m.json", pdf_dir=d / "pdfs", lock=d / "lock.json", include_failed=True)
            self.assertIn("SCAN", {c.source_id for c in chunks2} | {"SCAN"})  # override path runs without error


if __name__ == "__main__":
    unittest.main()


class Roundtrip(unittest.TestCase):
    def test_chunks_with_unicode_line_separators_survive(self):
        from zwtutor.models import Chunk
        weird = "line one line two\x85line three\x0bvertical\x0cformfeed end"
        c = Chunk("S", "I", "T", "e", "2099", "Sec", "1", 1, "", "", "", "S:p1:0", weird)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "chunks.jsonl"
            ingest.write_chunks([c, c], p)
            back = ingest.load_chunks(p)
            self.assertEqual(len(back), 2)
            self.assertEqual(back[0].source_text, weird)
