# Benchmark: this tutor vs plain Gemini

Purpose: show, on the same questions, what the retrieval + gate + verification layers add over "Gemini with a medical prompt". Do this honestly; report failures.

## Protocol
1. Use the labelled questions in `eval/questions.jsonl` (grounded, ungrounded, ambiguous, adversarial, citation traps).
2. **Plain Gemini:** the "Tutor vs plain Gemini" tab (or the same prompt in AI Studio): "You are a nursing tutor in Zimbabwe. Answer: <question>". No sources.
3. **This tutor:** `python eval/run_eval.py` (full) - results in `eval/results_full.json`.
4. A person scores each answer against the real PDF: correct / partly correct / wrong / refused; whether a citation was given; whether each cited passage supports the claim.
5. Report per category: wrong-answer rate on ungrounded questions (plain vs tutor), refusal rate on grounded questions (over-refusal), and unsupported numbers found.

## Demo-question selection log (fill in; do not cherry-pick silently)
| Question ID | Why chosen | Plain Gemini result | Tutor result |
|---|---|---|---|
| | | | |

State in the demo how the demo questions were chosen. The evaluation set is small (30); report counts, not percentages presented as proof.
