"""Unit tests for zwtutor.verify. All medical content is INVENTED."""
import unittest

from zwtutor.models import Chunk
from zwtutor.verify import (VClaim, claim_overlap, extract_quantities, locate_quote, unsupported_numbers,
                            verify_claim, verify_memory_aid, verify_quote)


def mk(cid, text, section="Doc > 1 Dosing"):
    return Chunk(source_id="S", institution="I", document_title="T", edition="e", publication_year="2099",
                 section=section, page_number="1", pdf_page=1, document_url="", licence_or_reuse_status="",
                 clinical_topic="", chunk_id=cid, source_text=text)


C1 = mk("S:p1:0", "Give Zorbex 5 mg twice daily for 7 days. Monitor the pulse every 4 hours. Stop if the temp-\nerature exceeds 38.5 degrees.")
C2 = mk("S:p2:0", "Give Quillon 2.5 mg per kg once daily for 3 days to children under 5 years. BP 140/90 mmHg is high.")
BY = {c.chunk_id: c for c in (C1, C2)}


class Quotes(unittest.TestCase):
    def test_exact(self):
        self.assertTrue(verify_quote(C1, "Give Zorbex 5 mg twice daily for 7 days")[0])
    def test_whitespace_and_case(self):
        self.assertTrue(verify_quote(C1, "Give  Zorbex 5 mg\n twice daily for 7 days")[0])
    def test_hyphenated_linebreak(self):
        self.assertTrue(verify_quote(C1, "Stop if the temperature exceeds 38.5 degrees")[0])
    def test_fabricated(self):
        self.assertFalse(verify_quote(C1, "Give Zorbex 10 mg twice daily for 7 days")[0])
    def test_too_short(self):
        self.assertFalse(verify_quote(C1, "Give Zorbex 5")[0])
    def test_wrong_chunk(self):
        self.assertFalse(verify_quote(C2, "Give Zorbex 5 mg twice daily for 7 days")[0])
    def test_none_chunk(self):
        self.assertFalse(verify_quote(None, "anything at all here now")[0])
    def test_locate(self):
        raw = C1.source_text
        s, e = locate_quote(raw, "Stop if the temperature exceeds 38.5 degrees")
        self.assertIn("38.5", raw[s:e])


class Numbers(unittest.TestCase):
    def test_supported(self):
        self.assertEqual(unsupported_numbers("Give 5 mg twice daily for 7 days", [C1]), [])
    def test_wrong_dose(self):
        self.assertIn("10 mg", unsupported_numbers("Give 10 mg twice daily", [C1]))
    def test_wrong_unit(self):
        self.assertTrue(unsupported_numbers("Give 5 g twice daily", [C1]))
    def test_wrong_duration(self):
        self.assertTrue(unsupported_numbers("for 14 days", [C1]))
    def test_frequency_mismatch(self):
        self.assertTrue(unsupported_numbers("Give it three times daily", [C1]))
    def test_decimal_and_per_kg(self):
        self.assertEqual(unsupported_numbers("2.5 mg per kg once daily for 3 days", [C2]), [])
        self.assertTrue(unsupported_numbers("25 mg per kg", [C2]))
    def test_bp_pair(self):
        self.assertEqual(unsupported_numbers("BP of 140/90 mmHg", [C2]), [])
        self.assertTrue(unsupported_numbers("BP of 160/100 mmHg", [C2]))
    def test_number_word(self):
        self.assertEqual(unsupported_numbers("for seven days", [C1]), [])
        self.assertTrue(unsupported_numbers("for ten days", [C1]))
    def test_no_arithmetic(self):
        # 2.5 mg/kg for a 10 kg child = 25 mg is arithmetic, and must NOT be silently accepted
        self.assertTrue(unsupported_numbers("Give 25 mg", [C2]))
    def test_years_and_labels_ignored(self):
        self.assertEqual(unsupported_numbers("See step 3 in the 2099 edition", [C1]), [])
    def test_drug_code_ignored(self):
        self.assertEqual(extract_quantities("use 3TC and 5FU"), [])
    def test_range(self):
        self.assertEqual([q.value for q in extract_quantities("give 5-10 mg")], ["5-10"])


class Claims(unittest.TestCase):
    def cl(self, text, cid, quote):
        return VClaim(text, [{"chunk_id": cid, "quote": quote}])

    def test_good(self):
        r = verify_claim(self.cl("Zorbex is given 5 mg twice daily for 7 days.", "S:p1:0",
                                 "Give Zorbex 5 mg twice daily for 7 days"), BY, set(BY))
        self.assertTrue(r.verified, r.problems)
    def test_bad_number_with_good_quote(self):
        r = verify_claim(self.cl("Zorbex is given 50 mg twice daily.", "S:p1:0",
                                 "Give Zorbex 5 mg twice daily for 7 days"), BY, set(BY))
        self.assertFalse(r.verified)
    def test_bad_quote(self):
        r = verify_claim(self.cl("Zorbex is given.", "S:p1:0", "Zorbex must always be given intravenously here"), BY, set(BY))
        self.assertFalse(r.verified)
    def test_chunk_not_allowed(self):
        r = verify_claim(self.cl("Zorbex is given.", "S:p1:0", "Give Zorbex 5 mg twice daily for 7 days"), BY, {"S:p2:0"})
        self.assertFalse(r.verified)
    def test_no_citation(self):
        self.assertFalse(verify_claim(VClaim("Zorbex.", []), BY, set(BY)).verified)
    def test_unrelated_claim_low_overlap(self):
        r = verify_claim(self.cl("Malaria vaccination protects against cholera outbreaks in refugees.", "S:p1:0",
                                 "Give Zorbex 5 mg twice daily for 7 days"), BY, set(BY))
        self.assertFalse(r.verified)
        self.assertLess(claim_overlap("Malaria vaccination protects refugees", [C1]), 0.5)


class Aid(unittest.TestCase):
    def pts(self, *verified):
        from zwtutor.verify import ClaimResult
        texts = ["Look at the patient", "Listen for breathing", "Touch the skin"]
        return [ClaimResult(t, v, []) for t, v in zip(texts, verified)]

    def aid(self, text="LLT", idx=(0, 1, 2), words=("Look", "Listen", "Touch")):
        return {"text": text, "letters": [{"stands_for": w, "point_index": i} for w, i in zip(words, idx)]}

    def test_ok(self):
        a, why = verify_memory_aid(self.aid(), self.pts(True, True, True))
        self.assertIsNotNone(a, why)
    def test_unverified_point(self):
        self.assertIsNone(verify_memory_aid(self.aid(), self.pts(True, False, True))[0])
    def test_wrong_letter(self):
        self.assertIsNone(verify_memory_aid(self.aid("LXT"), self.pts(True, True, True))[0])
    def test_word_not_in_point(self):
        self.assertIsNone(verify_memory_aid(self.aid(words=("Look", "Listen", "Taste")), self.pts(True, True, True))[0])
    def test_digits(self):
        self.assertIsNone(verify_memory_aid(self.aid("LL2"), self.pts(True, True, True))[0])
    def test_none(self):
        self.assertEqual(verify_memory_aid(None, [])[0], None)


if __name__ == "__main__":
    unittest.main()
