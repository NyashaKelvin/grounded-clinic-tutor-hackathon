# Zimbabwe Nursing Tutor

A study aid for Zimbabwean nursing students that answers **only** from a curated set of Zimbabwean sources, shows the exact passage, page and edition behind every point, and **visibly refuses** when the sources do not cover the question. Every quote and number is checked by code before it is shown.

*Hack for Humanity Harare 2026 - Challenge: **Best Use of the Google Gemini API***

## Problem

Nursing students in Zimbabwe often study from scattered, photocopied or outdated material and have little access to educators for real-time clarification. Generic chatbots answer confidently from foreign training data, with no way to check the answer against the guidelines a Zimbabwean nurse is actually examined on and works by. A fluent wrong answer is more dangerous than no answer.

**Intended user:** a nursing student (or tutor) learning from approved Zimbabwean guidelines. It is **not** for real-patient decisions.

## Solution

Students ask a study question, pick how they want to learn it (Explain, Teach me, Simplify, Memory aid, Quiz, Exam style, Flashcards, Compare, Case study, Teach-back, or just show the sources) and get:

- a cited answer where each point links to the source passage (highlighted quote, institution, title, edition, year, section, page, retrieved date, currency status);
- one of several **distinct refusal states**: not in the approved sources, sources differ, out of scope (e.g. patient-specific dosing), could not verify, possible emergency, personal information detected, or needs more detail;
- a topic browser built from the documents' own headings, an optional cartoon-style read-aloud voice, and a side-by-side "this tutor vs plain Gemini" tab.

## How it works

```
question -> pre-check (privacy / emergency / scope, no model) -> retrieval (Gemini embeddings + BM25 keywords)
         -> deterministic evidence gate (below threshold: the answering model is never called)
         -> Gemini structured JSON (chunk_id restricted to retrieved passages, exact quotes required)
         -> code verification (quote exists verbatim, numbers printed with same unit, claim words present, memory aid tied to verified points)
         -> cited answer, or CANNOT_VERIFY with the passages shown
```

The state (GROUNDED, NOT_IN_CORPUS, ...) is chosen by code. The model cannot upgrade a refusal to an answer.

## Gemini integration

Gemini is used in three places, all through the official `google-genai` SDK:

- **Embeddings** - `zwtutor/embed.py` (`gemini-embedding-001`, retrieval task types) for semantic search over the source chunks.
- **Answer generation** - `zwtutor/generate.py` (`generate_content` with a JSON schema whose `chunk_id` is an enum of this request's passages). Only reached after the pre-check and evidence gate pass. Retries a busy model once, then a fallback model; never retries rate limits in a loop.
- **Read-aloud** - `zwtutor/voice.py` (Gemini TTS preview, with a browser-voice fallback). It only reads text that already passed verification.

`tutor.py` (`call_gemini()`) is the earlier paste-your-own-material mode, kept as `app_paste_mode.py`; its error translation is reused by the new pipeline.

## Tech stack

Python 3.10+, Streamlit, google-genai, python-dotenv, NumPy, PyMuPDF. Default answer model `gemini-2.5-flash` (`GEMINI_MODEL` in `.env`).

## Run locally

1. `python -m venv .venv`
2. Activate it: Windows `.venv\Scripts\activate` (PowerShell: `.venv\Scripts\Activate.ps1`), macOS/Linux `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and put your key from [Google AI Studio](https://aistudio.google.com/) after `GEMINI_API_KEY=` (or type it in the app sidebar).
5. `python test_gemini.py` - one-request check that your key and SDK work.
6. **Get the sources:** `python scripts/download_corpus.py` downloads the PDFs listed in `corpus/manifest.json` into `corpus/pdfs/` (they are not stored in git; check each licence). Open each PDF's first page and correct the manifest fields (edition, year, issuer) if they differ.
7. **Build the index:** `python -m zwtutor.build` (chunks the PDFs with page and section metadata, embeds them, prints an identity-check report - read it).
8. `streamlit run app.py` - opens http://localhost:8501

### Check everything

- `python -m unittest discover -s tests -t .` - unit, pipeline and app tests (synthetic data, no key needed).
- `python harness.py` - checks this repo against the Build-Day Guide and the spec, and reports what still needs a human.
- `python eval/run_eval.py --no-generate` then `python eval/calibrate.py` - evaluation set and threshold calibration (needs the built index and a key).

## Safeguards and limitations

- **Educational support only.** Verify clinical decisions against current institutional guidelines and your educator; a notice is shown permanently. Do not enter patient-identifying information: obvious identifiers (names after "patient", phone numbers, IDs, emails) are blocked before anything is sent to the model, but this is pattern matching and will miss some.
- **Verification proves a quote exists and that numbers are printed in the source.** It does not prove that the explanation is a faithful reading of the passage. Numbers are matched as printed (same value and unit); no unit conversion or dose arithmetic is done or accepted.
- **Currency is not guaranteed.** Every source carries an edition, year and a currency status; all are `requires_verification` until a person confirms the current edition with the issuer. Sources may be superseded.
- **Tables and scanned pages** extract imperfectly; scanned pages without text are reported by the build and are not searchable (no OCR).
- **The gate thresholds are placeholders until calibrated** on the labelled evaluation set (the app shows a banner while they are). With ~30 questions the calibration is a small-sample estimate, not proof of accuracy.
- The conflict detector only reports a conflict the model raises AND two different verified sources support; it will miss conflicts the model does not notice.
- The cartoon voice is an original narrator style (not an imitation of any real character) using a preview TTS model; long passages may drift in quality. Sound is optional.
- Needs an internet connection; free-tier Gemini rate limits and occasional 503s apply. API keys are never written to code; `.env` is git-ignored.

### Not yet verified (read this before the demo)

The following were written but have **not been run against the live service or real documents** from the build environment (no key or PDFs were available there): live Gemini generation, live embeddings, live TTS, extraction quality on the real PDFs, and the gate thresholds. Everything else was tested with a synthetic corpus and a fake generator.

## Hack-Day build boundary

**Built during Hack Day (19 Sept 2026):** everything in `zwtutor/`, the new `app.py`, `scripts/download_corpus.py`, `corpus/manifest.json`, `eval/`, `tests/`, the updated `harness.py` and these docs.

**Pre-existing / carried over:** the earlier Node.js prototype (`node-prototype/`) and the paste-your-own-material Python mode (`tutor.py`, `app_paste_mode.py`), which were written earlier the same day for the same challenge. **PIVOT code** referred to in the team's brief has not been provided to this repository and none is included or claimed. If any pre-existing PIVOT code is added, list the files here and keep them separate from the Hack-Day work.

**Libraries/frameworks used (not written by us):** Streamlit, google-genai, python-dotenv, NumPy, PyMuPDF, httpx and pydantic (SDK dependencies), and the Gemini models.

**AI-assisted material:** the code, prompts and documentation in this repository were written with the help of Claude (Anthropic). The `sample/hyperkalemia.txt` sheet and all `tests/` fixtures contain **invented** content for testing and are not clinical references.

**Source documents:** none are redistributed here. See `corpus/manifest.json` for issuer, URL, reuse status and currency status of each, all marked `requires_verification`.

## Team

- TODO: add team member names and roles (guide Appendix E: problem lead, builder, prompt/test lead, UX/docs lead)

## Documentation

- [`docs/DESIGN_WORKSHEET.md`](docs/DESIGN_WORKSHEET.md) - problem -> user -> gap -> Gemini role -> safeguards
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) - timed demo, including the failure case and what we learned
