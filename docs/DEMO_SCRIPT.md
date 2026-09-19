# Demo script (2-3 minutes)

Structure from the guide (section 17). Show the **running app**, not slides.

| Time | Show | Say |
|---|---|---|
| 0:00-0:20 | Problem | Nursing students in under-resourced programmes study from photocopied material with little instructor access. Generic AI answers confidently even when wrong - in this domain that's dangerous. |
| 0:20-0:40 | User + input | Our user is a nursing student. Click **Load hyperkalemia example** - this is the trusted material they give the app. |
| 0:40-1:30 | Live workflow | Ask *"What do I do first for a patient with potassium of 7.8?"* -> green badge, explanation, big mnemonic (Calcium -> Insulin/dextrose -> Binder), and the quoted passage from the sheet. |
| 1:30-2:00 | Gemini integration | Point to `call_gemini()` in `tutor.py`: one call to Gemini with a system instruction and structured JSON output. Gemini writes the explanation and mnemonic and decides if the material answers the question. |
| 2:00-2:30 | Output / impact | The student gets a memory aid tied to a source they trust, and can see which sentence it came from. |
| 2:30-2:50 | Risk / safeguard | Click **Try: not in the material** (furosemide dose) -> red "Not found" badge. Say: *"This is the part most AI tutors don't do - ours tells you when it doesn't know, instead of guessing."* Mention the permanent disclaimer and that we verify the quote in code. |
| 2:50-3:00 | Learning | TODO (team): one thing that failed or changed today and what you learned. Example prompt: what did the model do the first time it was asked something out of scope, and what did you change? |

## Before you present

- Run `python test_gemini.py`, then `python harness.py`; fix anything red.
- Keep backup screenshots of the green and red results in case the internet drops.
- Test the exact path twice. Free-tier rate limits are real - don't spam the button.
- Know the OrganizerHQ deadline and submit before it.
- Never show or screenshot your API key.

## Submission information (OrganizerHQ)

- **Project name:** Grounded Clinical Reasoning Tutor
- **Description:** A study aid that explains clinical protocols and builds mnemonics only from course material the student supplies, and visibly refuses when the material doesn't cover the question.
- **Technologies:** Python, Streamlit, Google Gemini API (google-genai), python-dotenv
- **Repository link:** TODO (team)
- **Team information:** Leroy Mapunzwana, Nyasha Madoro, Euclide Mtisi, Ethel Kuvirima
- **Challenge:** Best Use of the Google Gemini API
