# One-page design worksheet

*(Guide section 13: Problem -> User -> Evidence -> Existing Solution -> Gap -> Gemini Capability -> Prototype -> Impact -> Risks/Safeguards)*

| Question | Team answer |
|---|---|
| Problem | Nursing students can't reliably check emergency clinical protocols (e.g. hyperkalemia sequencing) when studying from incomplete or photocopied material with little instructor access. |
| User | A nursing student in an under-resourced programme, studying from their own verified notes. |
| Evidence | TODO (team): add one real source or a first-hand observation, e.g. a conversation with a student or lecturer. Do not present a statistic you haven't verified. |
| Current approach | Re-reading photocopies, asking classmates, or asking a general chatbot that answers from its own training data. |
| Gap | Generic chatbots sound confident with no link to a trusted source; nothing tells the student when the answer is *not* supported by their material. |
| Gemini role | Reads the pasted material and the question, writes a plain-language explanation and a mnemonic, quotes the supporting passage, and decides whether the material actually answers the question (structured JSON output). |
| Input | Pasted verified course material + a plain-language question. |
| Output | Explanation, mnemonic, supporting quote, and a grounding badge (grounded / not found / unverified). |
| Safeguard | System instruction restricts Gemini to the supplied text; refusal is a first-class state; the quoted passage is verified against the source in code; permanent disclaimer; friendly handling of API failures. Known limit: the check does not prove the explanation is faithful to the quote. |
| Demo | 60-120 s: paste sheet -> in-scope question (green, mnemonic) -> out-of-scope question (red, refuses) -> stop. See `DEMO_SCRIPT.md`. |

**Gemini capability chosen (one, not all):** structured outputs over text reasoning/extraction.
