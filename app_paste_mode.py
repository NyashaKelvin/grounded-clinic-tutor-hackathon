"""Grounded Clinical Reasoning Tutor - Streamlit app.

Flow (guide section 1):  USER -> STREAMLIT PAGE -> PYTHON (tutor.py) -> GEMINI API -> PYTHON -> STREAMLIT RESULT
"""
import html
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

import tutor  # imported as a module so tests can swap tutor.ask_tutor

load_dotenv()

SAMPLE = Path(__file__).parent / "sample" / "hyperkalemia.txt"
SAMPLE_QUESTIONS = {
    "In the material": "What do I do first for a patient with potassium of 7.8?",
    "Not in the material": "What dose of furosemide should I give for hyperkalemia?",
}

st.set_page_config(page_title="Grounded Clinical Tutor", page_icon="🩺", layout="wide")
st.markdown(
    """<style>
    .mnemonic{font-size:1.9rem;font-weight:800;text-align:center;padding:1rem;border:2px dashed #1b5fd1;border-radius:12px;white-space:pre-wrap}
    </style>""",
    unsafe_allow_html=True,
)

st.title("🩺 Grounded Clinical Reasoning Tutor")
st.caption("Explains protocols and builds memory aids **only** from material you trust - and tells you when it can't.")
# Always visible (spec section 5.4)
st.warning("AI-generated study aid. Verify against your course material and instructor before clinical use.", icon="⚠️")

# ---- sidebar: API key (guide section 10, options A + B) --------------------
env_key = os.getenv("GEMINI_API_KEY", "").strip()
typed_key = st.sidebar.text_input("Gemini API key", type="password", help="Never written to disk or shown again. Or set GEMINI_API_KEY in .env.")
api_key = typed_key.strip() or env_key
if typed_key.strip():
    st.sidebar.caption("Using the key you typed.")
elif env_key:
    st.sidebar.caption("Using GEMINI_API_KEY from the environment/.env file.")
else:
    st.sidebar.caption("No key yet. Get one at aistudio.google.com -> Dashboard -> API Keys.")
st.sidebar.markdown("---")
st.sidebar.caption(f"Model: `{tutor.model_name()}`")
st.sidebar.caption("Needs an internet connection. Your text and result are kept only for this browser session - refreshing the page clears them.")

# ---- inputs ------------------------------------------------------------------
st.session_state.setdefault("source", "")
st.session_state.setdefault("question", "")


def load_sample():
    st.session_state["source"] = SAMPLE.read_text(encoding="utf-8")
    if not st.session_state["question"]:
        st.session_state["question"] = SAMPLE_QUESTIONS["In the material"]


def set_question(q):
    st.session_state["question"] = q


left, right = st.columns(2)
with left:
    st.subheader("1. Your verified course material")
    st.button("Load hyperkalemia example", on_click=load_sample)
    st.text_area("Paste a textbook excerpt, lecture note or protocol sheet", key="source", height=340)
with right:
    st.subheader("2. Your question")
    st.text_area("Ask about the material you pasted", key="question", height=100,
                 placeholder="e.g. What do I do first for a patient with potassium of 7.8?")
    ask = st.button("Ask", type="primary")
    c1, c2 = st.columns(2)
    c1.button("Try: in the material", on_click=set_question, args=(SAMPLE_QUESTIONS["In the material"],))
    c2.button("Try: not in the material", on_click=set_question, args=(SAMPLE_QUESTIONS["Not in the material"],))

# ---- ask Gemini ---------------------------------------------------------------
if ask:
    try:
        with st.spinner("Gemini is reading your material..."):
            st.session_state["answer"] = tutor.ask_tutor(api_key, st.session_state["source"], st.session_state["question"])
        st.session_state.pop("error", None)
    except tutor.TutorError as err:
        st.session_state.pop("answer", None)
        st.session_state["error"] = (err.user_message, err.detail)

# ---- results ------------------------------------------------------------------
if "error" in st.session_state:
    msg, detail = st.session_state["error"]
    st.error(msg)
    if detail:
        st.caption(detail[:300])

ans = st.session_state.get("answer")
if ans:
    st.divider()
    if ans.status == "grounded":
        st.success("✅ Grounded in your material")
    elif ans.status == "not_found":
        st.error("⚠️ Not found in provided material - verify independently")
    else:
        st.warning("⚠️ Partly unverified - the supporting quote wasn't found in your material. Check it yourself.")

    st.markdown("**Explanation**")
    st.write(ans.explanation)

    if ans.mnemonic:
        st.markdown("**Mnemonic**")
        st.markdown(f'<div class="mnemonic">{html.escape(ans.mnemonic)}</div>', unsafe_allow_html=True)
    if ans.source_excerpt_used:
        with st.expander("Passage from your material", expanded=True):
            st.text(ans.source_excerpt_used)
    if ans.confidence_note:
        st.info(ans.confidence_note)
    if ans.truncated:
        st.caption("This answer was long, so it has been shortened to stay readable.")
    for n in ans.notes:
        st.caption(n)

st.divider()
st.caption("Limitations: grounding is prompt-enforced plus a check that the quoted passage exists in your text. "
           "It does not prove the explanation is faithful to that passage. Single worked example, no accounts or history.")
