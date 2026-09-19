import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.check_deploy_ready import check
from tests.fixtures import make_pdf, source_entry
from zwtutor import ingest
from zwtutor.embed import HashingEmbedder, GeminiEmbedder
from zwtutor.index import build_index


class Deploy(unittest.TestCase):
    def _repo(self, td, embedder):
        d = Path(td)
        (d / "corpus" / "pdfs").mkdir(parents=True)
        make_pdf(d / "corpus" / "pdfs" / "SYNTH.pdf")
        ch, _ = ingest.ingest_pdf(d / "corpus" / "pdfs" / "SYNTH.pdf", source_entry())
        ingest.write_chunks(ch, d / "corpus" / "chunks.jsonl")
        build_index(ch, embedder, d / "corpus")
        (d / "corpus" / "manifest.json").write_text("{}")
        (d / "requirements.txt").write_text("streamlit\ngoogle-genai\npython-dotenv\nnumpy\npymupdf\n")
        subprocess.run(["git", "init", "-q"], cwd=d)
        return d

    def test_flags_test_embedder_pdfs_and_uncommitted_index(self):
        with tempfile.TemporaryDirectory() as td:
            d = self._repo(td, HashingEmbedder())
            subprocess.run(["git", "add", "-f", "corpus/pdfs/SYNTH.pdf"], cwd=d)
            res = check(d)
            text = " | ".join(m for _, m in res)
            self.assertIn("TEST-ONLY", text)
            self.assertIn("must not be uploaded", text)
            self.assertIn("is not committed", text)

    def test_ready_when_index_committed_and_no_pdf(self):
        with tempfile.TemporaryDirectory() as td:
            class Fake(HashingEmbedder):
                name = "gemini-embedding-001@1024"
            d = self._repo(td, Fake())
            subprocess.run(["git", "add", "corpus/chunks.jsonl", "corpus/vectors.npy", "corpus/index_meta.json", "requirements.txt"], cwd=d)
            res = check(d)
            self.assertFalse([m for s, m in res if s == "FAIL"], res)
            self.assertTrue(any("reuse status" in m for s, m in res))  # licence reminder is always shown


if __name__ == "__main__":
    unittest.main()
