import unittest
from eval.calibrate import choose
from eval.run_eval import load_questions, summarise


class E(unittest.TestCase):
    def test_question_set_shape(self):
        qs = load_questions()
        self.assertEqual(len(qs), 30)
        from collections import Counter
        c = Counter(q["category"] for q in qs)
        self.assertEqual(c, {"grounded": 10, "ungrounded": 6, "ambiguous": 4, "adversarial": 6, "citation_trap": 4})
        self.assertTrue(all(not q["labelled"] for q in qs if q["category"] == "grounded"))  # must be human-labelled

    def test_choose_refuses_all_negatives(self):
        pos = [(0.8, 1.0), (0.75, 0.9), (0.7, 0.8)]
        neg = [(0.6, 0.5), (0.72, 0.2)]
        ts, tc, kept, fp = choose(pos, neg, [x / 100 for x in range(50, 90, 2)], [x / 10 for x in range(0, 11)])
        self.assertEqual(fp, 0)
        self.assertEqual(kept, 3)

    def test_summary_flags_false_pass(self):
        rows = [{"id": "U1", "category": "ungrounded", "state": "GROUNDED", "expect_state": "NOT_IN_CORPUS", "labelled": True, "hit_at_k": None}]
        self.assertEqual(summarise(rows)["should_refuse_but_passed"], ["U1"])


if __name__ == "__main__":
    unittest.main()


class Pre(unittest.TestCase):
    def test_adversarial_and_ambiguous_prechecks(self):
        from zwtutor.safety import precheck
        for q in load_questions():
            if q["category"] in ("adversarial", "ambiguous") and q["expect_state"] in (
                    "EMERGENCY", "OUT_OF_SCOPE", "PRIVACY_BLOCKED", "NEEDS_CLARIFICATION"):
                self.assertEqual(precheck(q["question"]).state.value, q["expect_state"], q["id"])
