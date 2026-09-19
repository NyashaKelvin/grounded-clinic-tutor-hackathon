import unittest
from zwtutor.models import State, TutorResult
from zwtutor.voice import _split, browser_voice_html, pcm_to_wav, speakable_text


class V(unittest.TestCase):
    def test_reads_only_verified(self):
        r = TutorResult(State.GROUNDED, "explain", answer="Summary here.",
                        points=[{"text": "Verified point.", "verified": True}, {"text": "Unverified.", "verified": False}])
        t = speakable_text(r)
        self.assertIn("Verified point", t)
        self.assertNotIn("Unverified", t)

    def test_refusal_reads_fixed_message(self):
        r = TutorResult(State.NOT_IN_CORPUS, "explain", message="Not covered.", points=[{"text": "leak", "verified": True}])
        self.assertEqual(speakable_text(r), "Not covered.")

    def test_split_and_wav(self):
        parts = _split("Sentence one. " * 100)
        self.assertTrue(all(len(p) <= 760 for p in parts))
        self.assertTrue(pcm_to_wav(b"\x00\x00" * 100).startswith(b"RIFF"))

    def test_html_escapes_script_end(self):
        h = browser_voice_html('x</script><b>')
        self.assertNotIn('x</script><b>', h.split("const u=")[1])


if __name__ == "__main__":
    unittest.main()


class Conversational(unittest.TestCase):
    def _res(self):
        from types import SimpleNamespace as NS
        ch = NS(document_title="National HIV Guidelines", page_number="12")
        cite = NS(verified=True, chunk=ch)
        bad = NS(verified=False, chunk=ch)
        return TutorResult(State.GROUNDED, "explain", answer="Short summary.", points=[
            {"text": "Give the baby prophylaxis at birth.", "verified": True, "citations": [cite]},
            {"text": "Continue for six weeks.", "verified": True, "citations": [cite]},
            {"text": "UNVERIFIED CLAIM should never be spoken.", "verified": False, "citations": [bad]}])

    def test_sounds_like_talking_and_keeps_facts(self):
        from zwtutor.voice import speech_script
        t = speech_script(self._res())
        self.assertIn("give the baby prophylaxis at birth", t.lower())
        self.assertEqual(t.count("National HIV Guidelines"), 1)  # source said once, not repeated
        self.assertIn("continue for six weeks", t.lower())
        self.assertNotIn("UNVERIFIED", t)
        self.assertIn("First,", t)
        self.assertIn("And finally,", t)
        self.assertIn("National HIV Guidelines, page 12", t)
        self.assertTrue(t.rstrip().endswith(("?", ".")))

    def test_no_new_numbers_are_introduced(self):
        import re
        from zwtutor.voice import speech_script
        t = speech_script(self._res(), with_sources=False)
        self.assertEqual(re.findall(r"\d+", t), [])  # the wrapper adds no digits; page numbers only in source phrases

    def test_refusal_is_friendly_but_uses_the_fixed_message(self):
        from zwtutor.voice import speech_script
        from zwtutor import messages as M
        r = TutorResult(State.NOT_IN_CORPUS, "explain", message=M.NOT_IN_CORPUS)
        t = speech_script(r)
        self.assertTrue(t.startswith("Hmm"))
        self.assertIn(M.NOT_IN_CORPUS, t)

    def test_deterministic(self):
        from zwtutor.voice import speech_script
        self.assertEqual(speech_script(self._res()), speech_script(self._res()))
