"""Zimbabwe Nursing Tutor - Streamlit app (Hack for Humanity Harare 2026, Best Use of the Google Gemini API).

USER -> STREAMLIT -> zwtutor.pipeline (pre-check -> retrieve -> evidence gate -> Gemini -> verify) -> STREAMLIT
The app never shows model text that failed verification.
"""
import html
import os

import streamlit as st
from dotenv import load_dotenv

import tutor as legacy  # TutorError + Gemini error translation
from zwtutor import messages as M
from zwtutor import runtime, voice
from zwtutor.models import State
from zwtutor.schema import MODES
from zwtutor.verify import locate_quote

load_dotenv()
st.set_page_config(page_title="Zimbabwe Nursing Tutor", page_icon="🩺", layout="wide")
st.markdown("""<style>
.badge{display:inline-block;padding:.25rem .7rem;border-radius:999px;font-weight:700;font-size:.9rem;margin:.2rem 0}
.b-ok{background:#d8f5df;color:#0b5c22}.b-warn{background:#fff0c9;color:#7a4b00}.b-bad{background:#fde0e0;color:#8a1111}
.passage{background:#f6f7f9;border-left:4px solid #9aa4b2;padding:.6rem .8rem;border-radius:6px;font-size:.92rem;white-space:pre-wrap;color:#1f2933}
.passage mark{background:#ffe27a;padding:0 2px}
.aid{font-size:2rem;font-weight:800;text-align:center;padding:.8rem;border:2px dashed #1b5fd1;border-radius:12px}
</style>""", unsafe_allow_html=True)

STATE_LOOK = {
    State.GROUNDED: ("Answered from the approved sources", "b-ok"),
    State.NOT_IN_CORPUS: ("Not in the approved sources", "b-warn"),
    State.CONFLICTING_SOURCES: ("Sources differ", "b-warn"),
    State.OUT_OF_SCOPE: ("Out of scope", "b-bad"),
    State.CANNOT_VERIFY: ("Could not verify", "b-warn"),
    State.EMERGENCY: ("Possible emergency", "b-bad"),
    State.NEEDS_CLARIFICATION: ("Need more detail", "b-warn"),
    State.PRIVACY_BLOCKED: ("Blocked: personal information", "b-bad"),
}
EXAMPLES = ["What does the national guideline say about PMTCT for a breastfeeding mother?",
            "What are the danger signs to check for in the newborn after birth?",
            "Which infection prevention steps apply when handling sharps?",
            "What is the recommended treatment for uncomplicated malaria in adults?"]  # last one may be NOT covered: on purpose


def esc(s: str) -> str:
    return html.escape(s or "")


def show_passage(chunk, quote: str = ""):
    text = chunk.source_text
    span = locate_quote(text, quote) if quote else None
    body = (esc(text[:span[0]]) + "<mark>" + esc(text[span[0]:span[1]]) + "</mark>" + esc(text[span[1]:])) if span else esc(text)
    st.markdown(f'<div class="passage">{body}</div>', unsafe_allow_html=True)


def citation_line(c) -> str:
    ch = c.chunk
    return (f"{ch.institution}, *{ch.document_title}*, {ch.edition or 'edition not stated'}, {ch.publication_year or 'year not stated'} "
            f"- section: {ch.section or 'n/a'} - page {ch.page_label()} - retrieved {ch.retrieved_on or 'n/a'} - "
            f"currency: **{ch.currency_status.replace('_', ' ')}**")


def render_citations(cites, key: str):
    for i, c in enumerate(cites):
        mark = "verified quote" if c.verified else "QUOTE NOT VERIFIED"
        with st.expander(f"Source {i + 1}: {c.chunk.document_title[:60]} ({mark})"):
            st.markdown(citation_line(c))
            show_passage(c.chunk, c.quote if c.verified else "")
            if c.chunk.licence_or_reuse_status:
                st.caption(f"Reuse status: {c.chunk.licence_or_reuse_status}")


def render_hits(hits, title: str):
    if not hits:
        return
    st.markdown(f"**{title}**")
    for i, h in enumerate(hits):
        with st.expander(f"{h.chunk.document_title[:60]} - {h.chunk.section[:50]} (similarity {h.sem:.2f})"):
            st.markdown(citation_line(type("C", (), {"chunk": h.chunk})()))
            show_passage(h.chunk)


def render_result(r, key: str):
    label, cls = STATE_LOOK[r.state]
    st.markdown(f'<span class="badge {cls}">{label}</span>', unsafe_allow_html=True)
    if r.message:
        (st.error if cls == "b-bad" else st.warning)(r.message)
    if r.conflict:
        st.info("Difference: " + r.conflict["description"])
    if r.answer:
        st.markdown(r.answer)
    for i, p in enumerate(r.points):
        st.markdown(f"**{i + 1}.** {p['text']}")
        render_citations(p["citations"], f"{key}p{i}")
    if r.memory_aid:
        st.markdown(f'<div class="aid">{esc(r.memory_aid["text"])}</div>', unsafe_allow_html=True)
        for l in r.memory_aid["letters"]:
            st.markdown(f"- **{l['letter']}** = {l['stands_for']} (point {l['point_index'] + 1})")
    for i, q in enumerate(r.quiz):
        st.markdown(f"**Q{i + 1}. {q['question']}**")
        for o in q.get("options", []):
            st.markdown(f"- {o}")
        with st.expander("Show answer"):
            st.markdown(f"**{q['answer']}**  \n{q.get('explanation', '')}")
            render_citations(q["citations"], f"{key}q{i}")
    for i, c in enumerate(r.cards):
        with st.expander(f"Card {i + 1}: {c['front']}"):
            st.markdown(c["back"])
            render_citations(c["citations"], f"{key}c{i}")
    if r.state == State.GROUNDED and r.mode == "source":
        render_hits(r.evidence, "Closest source passages")
    elif r.state in (State.NOT_IN_CORPUS, State.CANNOT_VERIFY):
        render_hits(r.evidence[:3], "Closest passages found (shown so you can read them yourself; they do not answer the question)"
                    if r.state == State.NOT_IN_CORPUS else "Passages the answer was based on")
    for x in r.limitations:
        st.caption(x)
    if r.verification.get("problems"):
        with st.expander("Why verification failed"):
            for p in r.verification["problems"]:
                st.markdown(f"- {p}")
    if r.gate:
        with st.expander("Evidence check (for judges and educators)"):
            st.json(r.gate)
            st.caption(f"Answering model called: {'yes (' + r.model_used + ')' if r.generated else 'no'}")


def voice_controls(r, key: str, api_key: str):
    text = voice.speech_script(r)
    if not text.strip():
        return
    c1, c2 = st.columns([1, 2])
    with c1:
        v = st.selectbox("Voice", list(voice.VOICES), key=f"v{key}", label_visibility="collapsed")
        if st.button("Read aloud, cartoon voice", key=f"tts{key}"):
            try:
                with st.spinner("Warming up the voice..."):
                    st.session_state[f"aud{key}"] = voice.gemini_tts(text, voice.VOICES[v], api_key=api_key)
            except Exception:  # noqa: BLE001
                st.session_state[f"aud{key}"] = None
                st.session_state[f"fb{key}"] = True
    with c2:
        if st.session_state.get(f"aud{key}"):
            st.audio(st.session_state[f"aud{key}"], format="audio/wav", autoplay=True)
        if st.session_state.get(f"fb{key}"):
            st.caption("The Gemini voice is not available right now, so here is the browser voice instead.")
        if st.session_state.get(f"fb{key}") or st.session_state.get(f"aud{key}") is None:
            page = voice.browser_voice_html(text)  # text is JSON-escaped inside the script
            if hasattr(st, "iframe"):
                st.iframe(page, height=60)
            else:  # older Streamlit
                st.components.v1.html(page, height=60)


# ------------------------------------------------------------------ page
st.title("🩺 Zimbabwe Nursing Tutor")
st.info(M.EDUCATION_NOTICE)
st.warning(M.PRIVACY_WARNING)

with st.sidebar:
    st.header("Setup")
    key_in = st.text_input("Gemini API key", type="password", value="", help="Or put it in .env as GEMINI_API_KEY. Never committed to git.")
    api_key = key_in.strip() or runtime.get_key()
    strict = st.toggle("Strict verification", value=True, help="On: any failed quote or number check means no answer is shown.")
    st.caption("Needs an internet connection. Refreshing the page clears the current answer.")
    st.caption("Sources are teaching aids. Editions and currency status are shown with every citation.")

try:
    tutor_obj = st.cache_resource(runtime.load_tutor, show_spinner="Loading the source index...")(api_key, strict)
except runtime.SetupError as exc:
    st.error(str(exc))
    st.stop()
except legacy.TutorError as exc:
    st.error(exc.user_message)
    st.stop()

if not tutor_obj.cfg.calibrated:
    st.warning(M.UNCALIBRATED)

tab_ask, tab_browse, tab_bench, tab_src = st.tabs(["Ask the tutor", "Browse topics", "Tutor vs plain Gemini", "Sources"])

with tab_ask:
    ex = st.selectbox("Try an example (or type your own below)", [""] + EXAMPLES)
    q = st.text_area("Your study question", value=ex, height=90, max_chars=600, placeholder="e.g. What are the postnatal checks for a newborn?")
    mode = st.radio("How should I teach it?", list(MODES), format_func=lambda m: MODES[m][0], horizontal=True)
    if st.button("Ask", type="primary"):
        try:
            with st.spinner("Searching the sources and checking every quote..."):
                st.session_state["last"] = tutor_obj.ask(q, mode)
        except legacy.TutorError as exc:
            st.session_state["last"] = None
            st.error(exc.user_message)
            if exc.detail:
                with st.expander("Technical detail (for debugging)"):
                    st.code(str(exc.detail)[:600])
    r = st.session_state.get("last")
    if r:
        render_result(r, "a")
        voice_controls(r, "a", api_key)

with tab_browse:
    st.caption("Pick a section to study. Headings come from the documents themselves.")
    for t in tutor_obj.index.topics():
        with st.expander(t["title"]):
            for top, subs in t["sections"].items():
                if st.button(top[:90], key=f"tp{t['source_id']}{top}"):
                    st.session_state["browse_q"] = top
                    st.session_state["browse_t"] = t["source_id"]
    if st.session_state.get("browse_q"):
        topic = st.session_state["browse_q"]
        st.markdown(f"### {topic}")
        bm = st.radio("Mode", ["explain", "teach", "flashcards", "quiz", "source"], format_func=lambda m: MODES[m][0], horizontal=True, key="bm")
        if st.button("Study this", key="study"):
            try:
                with st.spinner("Working..."):
                    st.session_state["browse_r"] = tutor_obj.ask(f"Explain {topic}", bm)
            except legacy.TutorError as exc:
                st.error(exc.user_message)
        if st.session_state.get("browse_r"):
            render_result(st.session_state["browse_r"], "b")

with tab_bench:
    st.caption("Same question, two ways: plain Gemini with a medical prompt (no sources, no checks) vs this tutor.")
    bq = st.text_input("Question", value="What is the recommended first-line treatment for uncomplicated malaria in adults in Zimbabwe?")
    if st.button("Compare"):
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Plain Gemini")
            try:
                from google import genai
                cl = genai.Client(api_key=api_key)
                resp = cl.models.generate_content(model=getattr(tutor_obj.generator, "model", None) or runtime.generate.configured_model(),
                                                  contents="You are a nursing tutor in Zimbabwe. Answer: " + bq)
                st.write(resp.text)
                st.caption("No citations, no source check. It may be right or wrong, and you cannot tell which.")
            except Exception as exc:  # noqa: BLE001
                st.error(legacy.translate_exception(exc).user_message)
        with col2:
            st.subheader("This tutor")
            try:
                render_result(tutor_obj.ask(bq, "explain"), "c")
            except legacy.TutorError as exc:
                st.error(exc.user_message)

with tab_src:
    seen = {}
    for c in tutor_obj.index.chunks:
        seen.setdefault(c.source_id, c)
    for sid, c in seen.items():
        n = sum(1 for x in tutor_obj.index.chunks if x.source_id == sid)
        st.markdown(f"**{c.document_title}**  \n{c.institution} - {c.edition or 'edition not stated'} - {c.publication_year or 'year not stated'} - "
                    f"{n} passages - currency: **{c.currency_status.replace('_', ' ')}** - reuse: {c.licence_or_reuse_status or 'not stated'}  \n{c.document_url}")
