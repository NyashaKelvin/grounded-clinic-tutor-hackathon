# Zimbabwe Nursing Tutor

A study aid for Zimbabwean nursing students that answers **only** from a curated set of Zimbabwean sources, shows the exact passage, page and edition behind every point, and **visibly refuses** when the sources do not cover the question. Every quote and number is checked by code before it is shown.

*Hack for Humanity Harare 2026 - Challenge: **Best Use of the Google Gemini API***

**Participants:** Leroy Mapunzwana, Nyasha Madoro, Euclide Mtisi, Ethel Kuvirima

**Deployed app:** `[PLACEHOLDER: Streamlit Community Cloud URL]` (see [Deploy to Streamlit Community Cloud](#deploy-to-streamlit-community-cloud-no-rebuild-in-the-cloud)). It can also be run locally, see [Run locally](#run-locally).

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

## Project structure

```
app.py                  Streamlit app (the submitted UI)
app_paste_mode.py       earlier paste-your-own-material mode (kept for reference)
tutor.py                Gemini call + error translation used by paste mode and reused by the pipeline
zwtutor/                the tutor itself
  ingest.py             PDF -> passages with page, section and edition metadata
  embed.py              Gemini embeddings (+ a test-only offline embedder)
  index.py, retrieve.py hybrid search: meaning (embeddings) + keywords (BM25)
  gate.py               evidence gate: below the threshold the answering model is never called
  safety.py             privacy / emergency / scope pre-checks (no AI)
  schema.py, generate.py  Gemini structured answers, modes, model auto-discovery
  verify.py             quote / number / claim / memory-aid verification
  pipeline.py           question -> pre-check -> retrieve -> gate -> generate -> verify -> result
  voice.py              conversational read-aloud (Gemini TTS + browser fallback)
  runtime.py, build.py  loading the index; `python -m zwtutor.build`
corpus/chunks.jsonl, vectors.npy, index_meta.json   the built search index (committed so deployment needs no rebuild)
corpus/manifest.json    the list of approved sources (issuer, URL, edition, reuse and currency status)
scripts/                download_corpus.py, smoke_live.py, list_models.py, check_deploy_ready.py
eval/                   30-question evaluation set, run_eval.py, calibrate.py
tests/                  automated tests (synthetic data, no key needed)
docs/                   design worksheet, demo script, benchmark protocol
harness.py              checks the repo against the hackathon guide
requirements.txt        dependencies
.env.example            template for your key (copy to .env; .env is git-ignored)
node-prototype/         first prototype in Node.js (not part of the submitted app)
```

## Tech stack

Python 3.10+, Streamlit, google-genai, python-dotenv, NumPy, PyMuPDF. Default answer model `gemini-2.5-flash` (`GEMINI_MODEL` in `.env`).

## Run locally

You need Python 3.10 or newer and a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

1. Get the code: `git clone <this repository's URL>` then `cd` into the folder.
2. Create and activate a virtual environment:
   - `python -m venv .venv`
   - Windows: `.venv\Scripts\activate` (PowerShell: `.venv\Scripts\Activate.ps1`); macOS/Linux: `source .venv/bin/activate`
3. Install the dependencies: `pip install -r requirements.txt`
   *(with [uv](https://docs.astral.sh/uv/) instead: `uv venv`, `uv pip install -r requirements.txt`, and put `uv run` before the commands below)*
4. Add your key: copy `.env.example` to `.env` and put the key after `GEMINI_API_KEY=`. **Never commit `.env`**; it is git-ignored. (Or type the key into the app's sidebar.)
5. `python scripts/smoke_live.py` - checks that your key works for embeddings, answers and voice. `python scripts/list_models.py` shows which models your key can use if you need to set `GEMINI_MODEL`.
6. **Get the sources:** `python scripts/download_corpus.py` downloads the PDFs listed in `corpus/manifest.json` into `corpus/pdfs/`. They are not stored in git; check each document's licence. Open each PDF's first page and correct the manifest fields (title, edition, year) if they differ.
7. **Build the index:** `python -m zwtutor.build` (takes several minutes on the free tier; if it stops, run it again and it resumes). Read the report it prints; sources that are unreadable or fail the identity check are left out.
8. **Start the app:** `streamlit run app.py` - opens http://localhost:8501

### Deploy to Streamlit Community Cloud (no rebuild in the cloud)

The built search index (`corpus/chunks.jsonl`, `corpus/vectors.npy`, `corpus/index_meta.json`, about 4 MB) is committed to the repository, so the deployed app starts immediately. The source PDFs are never committed.

1. Build locally first (steps 6-7 above) and test with `streamlit run app.py`.
2. `python scripts/check_deploy_ready.py` - must say "Ready to deploy". It checks the index, that no PDFs, `.env` or secrets are tracked, and lists each source's reuse status.
3. `git add corpus/chunks.jsonl corpus/vectors.npy corpus/index_meta.json`, commit and push.
4. At https://share.streamlit.io choose **Create app**, pick this repository, branch `main`, main file `app.py`. Under **Advanced settings** choose Python 3.12 or 3.13 and paste the contents of `.streamlit/secrets.toml.example` into **Secrets** with your real key.
5. Deploy, then put the app's URL in the "Deployed app" line at the top of this README and in your submission.

Notes: (a) every visitor spends *your* Gemini quota, so keep the per-session question limit and consider a separate key with a budget; (b) if you change the PDFs or the manifest, rebuild locally and commit the three index files again, since a stale index is rejected on start-up; (c) **the index contains passages of the source documents.** Check each source's reuse status (listed by the check script and in `corpus/manifest.json`) before making the repository or the app public. If you are not sure you may republish a source, keep the repository private (Streamlit Community Cloud can deploy private repositories) or leave that source out of the index.

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

**Source documents:** the PDFs are not stored here, but the committed search index contains passages of their text (see the Deploy notes on reuse status). See `corpus/manifest.json` for issuer, URL, reuse status and currency status of each, all marked `requires_verification`.

## Team

| Name | Role |
|---|---|
| Leroy Mapunzwana | Participant |
| Nyasha Madoro | Participant |
| Euclide Mtisi | Participant |
| Ethel Kuvirima | Participant |

*(Roles can be refined to the guide's suggested split: problem lead, builder, prompt and test lead, UX and docs lead.)*

## Documentation

- [`docs/DESIGN_WORKSHEET.md`](docs/DESIGN_WORKSHEET.md) - problem -> user -> gap -> Gemini role -> safeguards
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) - timed demo, including the failure case and what we learned
