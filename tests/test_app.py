"""Headless Streamlit test of the new app on the SYNTHETIC corpus with a fake generator."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from streamlit.testing.v1 import AppTest

from tests.fixtures import make_pdf, source_entry
from zwtutor import ingest, runtime
from zwtutor.embed import HashingEmbedder
from zwtutor.gate import GateConfig
from zwtutor.index import build_index


class FakeGen:
    calls = 0

    def __init__(self, *a, **k):
        pass

    def generate(self, prompt, schema):
        FakeGen.calls += 1
        cid = schema["properties"]["points"]["items"]["properties"]["citations"]["items"]["properties"]["chunk_id"]["enum"][0]
        chunk_text = prompt.split(f"[chunk_id: {cid}]")[1].split('"""')[1]
        quote = " ".join(chunk_text.split()[:8])
        return {"cannot_answer": False, "summary": "", "conflict": {"exists": False, "description": ""},
                "points": [{"text": "Synthetic point " + quote[:20], "citations": [{"chunk_id": cid, "quote": quote}]}]}, "fake"


class AppT(unittest.TestCase):
    def test_flow(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            (d / "pdfs").mkdir()
            make_pdf(d / "pdfs" / "SYNTH.pdf")
            chunks, _ = ingest.ingest_pdf(d / "pdfs" / "SYNTH.pdf", source_entry())
            ingest.write_chunks(chunks, d / "chunks.jsonl")
            build_index(chunks, HashingEmbedder(), d)
            with mock.patch.object(ingest, "CORPUS", d), mock.patch.object(ingest, "CHUNKS", d / "chunks.jsonl"), \
                 mock.patch.dict(os.environ, {"ALLOW_TEST_EMBEDDER": "1", "GEMINI_API_KEY": "test-key"}), \
                 mock.patch.object(runtime, "GeminiGenerator", FakeGen), \
                 mock.patch.object(runtime, "load_config", lambda: GateConfig(tau_sem=0.0, tau_cov=0.3)):
                at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30).run()
                self.assertFalse(at.exception, at.exception)
                self.assertTrue(any("Educational support only" in m.value for m in at.markdown))
                self.assertTrue(any("not been calibrated" in m.value for m in at.markdown))
                self.assertEqual(len(at.sidebar.children), 0, "no sidebar / key box when the key is configured")
                at.text_area[0].set_value("How is Zorbex dosed for adults?").run()
                at.button[0].click().run()
                self.assertFalse(at.exception, at.exception)
                self.assertEqual(FakeGen.calls, 1)
                self.assertTrue(any("Answered from the approved sources" in m.value for m in at.markdown))
                # visual aid: learning map with a tick per point and a progress bar
                self.assertTrue(any("0 of 1 points learned" in m.value for m in at.markdown))
                at.checkbox[0].check().run()
                self.assertTrue(any("1 of 1 points learned" in m.value for m in at.markdown))
                self.assertTrue(any('class="card done"' in m.value for m in at.markdown))
                # a privacy-blocked question must not reach the generator
                at.text_area[0].set_value("Patient John Moyo needs Zorbex, how is it dosed?").run()
                at.button[0].click().run()
                self.assertEqual(FakeGen.calls, 1)
                self.assertTrue(any("NOT sent to the AI" in m.value for m in at.markdown))


if __name__ == "__main__":
    unittest.main()


class NoKey(unittest.TestCase):
    def test_key_box_is_in_the_page_not_a_sidebar(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}), mock.patch.object(runtime, "get_key", lambda: ""):
            at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "app.py"), default_timeout=30).run()
            self.assertFalse(at.exception, at.exception)
            self.assertEqual(len(at.sidebar.children), 0)
            self.assertTrue(at.text_input and at.text_input[0].proto.type == 1)  # 1 = PASSWORD
            self.assertFalse(at.text_area)  # nothing else until a key is given
