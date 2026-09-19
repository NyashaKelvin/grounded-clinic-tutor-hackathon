# Grounded Clinical Reasoning Tutor

A study aid for nursing students that explains clinical protocols and generates mnemonics **only from course material the student supplies**, shows a visible grounding badge, and refuses to guess when the material doesn't cover the question.

*Hack for Humanity Harare 2026 - Challenge: **Best Use of the Google Gemini API***

## Problem

Nursing students in under-resourced programmes often study from incomplete or photocopied material, with little access to instructors for real-time clarification of protocols such as emergency drug sequencing. A wrong sequence or dose logic is the kind of error that follows a student into clinical practice.

Generic AI chatbots make this worse: they answer confidently from their own training data, with no way for the student to check that the answer traces back to a source they trust. In a safety-critical field, a fluent wrong answer is more dangerous than no answer.

**Intended user:** a nursing student studying from their own verified notes, textbook excerpt or protocol sheet.

## Solution

A Streamlit web app where the student:

1. pastes verified course material,
2. asks a plain-language question (e.g. *"What do I do first for a patient with potassium of 7.8?"*),
3. gets back a plain-language explanation, a mnemonic for that protocol, the exact passage it relied on, and a **grounding badge**: green (grounded), red (not in your material - verify independently) or amber (quote could not be verified).

Refusal is a first-class output, not an error. This is **not** a general medical chatbot.

## Gemini integration

The Gemini API is called in exactly one place: `call_gemini()` in [`tutor.py`](tutor.py), via the official `google-genai` SDK (`client.models.generate_content`). What Gemini adds is the reading comprehension: it turns the student's pasted material plus a question into a plain-language explanation and a tailored mnemonic, and judges whether the material actually answers the question.

- **System instruction** forces answers *only* from the supplied material and requires a refusal when it isn't covered.
- **Structured output** (`response_schema`) returns `grounded`, `explanation`, `mnemonic`, `source_excerpt_used`, `confidence_note` so the app can act on the result reliably.
- **Post-check** (`classify()`): if Gemini says "grounded", the app verifies the quoted passage really exists in the student's text; otherwise the badge downgrades to amber.
- **Resilience:** friendly messages for missing key, empty input, 401/403, 429, 503 and network loss; a busy model is retried once, then a fallback model is tried; 429s are never retried in a loop.

## Tech stack

Python 3.10+, [Streamlit](https://streamlit.io), [google-genai](https://pypi.org/project/google-genai/) (Gemini SDK), python-dotenv. Gemini model: `gemini-2.5-flash` by default (change with `GEMINI_MODEL` in `.env`).

## Run locally

1. `python -m venv .venv`
2. Activate it: Windows `.venv\Scripts\activate` (PowerShell: `.venv\Scripts\Activate.ps1`), macOS/Linux `source .venv/bin/activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and put your key from [Google AI Studio](https://aistudio.google.com/) (Dashboard -> API Keys) after `GEMINI_API_KEY=`. *Or* skip this and type the key into the app's sidebar box.
5. `python test_gemini.py` - one-request check that your key and SDK work
6. `streamlit run app.py` - opens http://localhost:8501

### Check everything

`python harness.py` runs an automated check of this project against the hackathon Beginner Build-Day Guide (files, secret hygiene, failure handling, the running app, live Gemini calls if a key is set) and prints what passed, failed, was skipped, and what still needs a human. `python harness.py --help` for options.

## Safeguards and limitations

What users should **not** assume:

- **Not medical advice.** AI-generated study aid - verify against your course material and instructor before clinical use (shown permanently in the app).
- Grounding is prompt-enforced plus a verbatim-quote check. The check proves the cited passage exists in your text, **not** that the explanation is faithful to it; a determined adversarial input could still mislead the model.
- The app is only as trustworthy as the material you paste in.
- One worked example (hyperkalemia), paste-only input (no file upload/OCR), no accounts or history. Refreshing the browser clears everything.
- Needs an internet connection; free-tier Gemini rate limits and occasional 503s apply.
- API keys are never written to code. `.env` and `.venv/` are git-ignored.

## Hack-Day build boundary

**Built during Hack Day:** the prompt design and refusal behaviour, `tutor.py` (Gemini call, validation, error handling, quote verification), `app.py` (Streamlit UI), `test_gemini.py`, `harness.py`, the docs in `docs/`, and the hyperkalemia teaching sheet in `sample/`.

**Libraries/frameworks used (not written by us):** Streamlit, google-genai, python-dotenv, httpx and pydantic (SDK dependencies), and the Gemini model itself.

**AI-assisted material:** the code, prompts and documentation in this repository were written with the help of Claude (Anthropic). The hyperkalemia sample sheet is illustrative teaching text, **not** a clinical reference, and must be replaced with the student's own verified material for real use.

**Earlier prototype:** `node-prototype/` is a first version of the same idea in Node.js, kept for reference. The submitted app is the Python/Streamlit one at the repository root.

## Team

- TODO: add team member names and roles (guide Appendix E: problem lead, builder, prompt/test lead, UX/docs lead)

## Documentation

- [`docs/DESIGN_WORKSHEET.md`](docs/DESIGN_WORKSHEET.md) - problem -> user -> gap -> Gemini role -> safeguards
- [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) - timed 2-3 minute demo, including the failure case and what we learned
