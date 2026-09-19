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
st.set_page_config(page_title="Zimbabwe Nursing Tutor", page_icon="+", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
:root{--ink:#1B2A32;--muted:#5B6B73;--line:#D9E1DE;--card:#FFFFFF;--brand:#0F5C63;--brand-soft:#E4F0EE;--gold:#B7791F;
--ok:#1F6B4A;--ok-bg:#E3F1EB;--warn:#8A5A12;--warn-bg:#FBF1DF;--bad:#8E2F2F;--bad-bg:#F8E6E6;--info:#2B5F8A;--info-bg:#E6EFF7}
.block-container{max-width:1080px;padding-top:2.2rem;padding-bottom:4rem}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{visibility:hidden;height:0}
h1{font-weight:750;letter-spacing:-.02em;color:var(--brand);margin-bottom:.1rem}
h3{color:var(--ink)}
.tagline{color:var(--muted);font-size:1.02rem;margin:0 0 1rem 0}
.notice{background:var(--brand-soft);border:1px solid #C9DEDA;border-left:4px solid var(--brand);border-radius:8px;padding:.7rem 1rem;color:var(--ink);font-size:.9rem;line-height:1.45;margin-bottom:1.1rem}
.notice small{display:block;color:var(--muted);margin-top:.35rem}
.badge{display:inline-block;padding:.28rem .8rem;border-radius:999px;font-weight:650;font-size:.85rem;margin:.2rem 0 .5rem 0;letter-spacing:.01em}
.b-ok{background:var(--ok-bg);color:var(--ok)}.b-warn{background:var(--warn-bg);color:var(--warn)}.b-bad{background:var(--bad-bg);color:var(--bad)}
.callout{border-radius:8px;padding:.8rem 1rem;margin:.2rem 0 .8rem 0;line-height:1.5;border:1px solid transparent}
.c-b-ok{background:var(--ok-bg);border-color:#BFDDCE}.c-b-warn{background:var(--warn-bg);border-color:#EBD6AE}.c-b-bad{background:var(--bad-bg);border-color:#E9C4C4}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:.85rem 1.05rem;box-shadow:0 1px 2px rgba(15,40,45,.04)}
.card.done{background:#F1F8F4;border-color:#BFDDCE}
.stext{font-size:1.02rem;line-height:1.55;color:var(--ink)}
.chip{display:inline-block;margin-top:.5rem;padding:.12rem .55rem;border-radius:6px;background:var(--brand-soft);color:var(--brand);font-size:.76rem;font-weight:600}
.prog{height:8px;background:#E3E9E7;border-radius:999px;overflow:hidden;margin:.3rem 0 .2rem 0}
.prog>div{height:100%;background:linear-gradient(90deg,var(--brand),#2E8C8F);border-radius:999px;transition:width .3s}
.progtext{font-size:.85rem;color:var(--muted);margin-bottom:.9rem}
.passage{background:#F4F6F5;border-left:4px solid #9DB3AF;padding:.7rem .9rem;border-radius:6px;font-size:.92rem;white-space:pre-wrap;color:var(--ink)}
.passage mark{background:#F6E2A6;padding:0 2px;border-radius:2px}
.aid{display:flex;gap:.6rem;flex-wrap:wrap;margin:.4rem 0 1rem 0}
.tile{min-width:92px;text-align:center;background:var(--card);border:1px solid var(--line);border-top:4px solid var(--brand);border-radius:10px;padding:.55rem .7rem}
.tile b{display:block;font-size:2rem;line-height:1.1;color:var(--brand)}
.tile span{display:block;font-size:.85rem;color:var(--ink);margin-top:.15rem}
.tile i{display:block;font-size:.72rem;color:var(--muted);font-style:normal;margin-top:.2rem}
.aidname{font-size:.85rem;color:var(--muted);margin-top:.6rem}
.qcard{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--gold);border-radius:10px;padding:.8rem 1rem;margin:.5rem 0 .2rem 0}
.stTabs [data-baseweb="tab"]{font-weight:600}
.stTabs [aria-selected="true"]{color:var(--brand)}
.stTabs [data-baseweb="tab-highlight"]{background-color:var(--brand)}
[data-testid="stBaseButton-primary"]{background:var(--brand);border-color:var(--brand);color:#fff;font-weight:650;border-radius:8px}
[data-testid="stBaseButton-primary"]:hover{background:#0B4A50;border-color:#0B4A50;color:#fff}
[data-testid="stBaseButton-secondary"]{border-radius:8px;border-color:var(--line);color:var(--ink)}
[data-testid="stBaseButton-secondary"]:hover{border-color:var(--brand);color:var(--brand)}
[data-testid="stBaseButton-pills"]{border-radius:999px;border-color:var(--line);background:#fff;color:var(--ink)}
[data-testid="stBaseButton-pills"]:hover{border-color:var(--brand);color:var(--brand)}
[data-testid="stBaseButton-pillsActive"]{border-radius:999px;background:var(--brand);border-color:var(--brand);color:#fff}
[data-testid="stCheckbox"] [data-baseweb="checkbox"] span[role="checkbox"]{border-color:var(--brand)}
div[data-testid="stCheckbox"] label p{font-size:.8rem;color:var(--muted)}
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
MAX_QUESTIONS_PER_SESSION = int(os.getenv("MAX_QUESTIONS_PER_SESSION", "40") or 40)
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


def short_src(c) -> str:
    ch = c.chunk
    title = ch.document_title if len(ch.document_title) <= 46 else ch.document_title[:45] + "..."
    return f"{title}  |  p. {ch.page_number or ch.pdf_page}"


def render_learning_map(r, key: str):
    """The visual aid: the verified points as a step-by-step map. Tick each one as you learn it;
    the card turns green and the progress bar fills. Text is shown exactly as verified."""
    n = len(r.points)
    learned = sum(1 for i in range(n) if st.session_state.get(f"got_{key}_{i}"))
    pct = int(100 * learned / n) if n else 0
    st.markdown(f'<div class="prog"><div style="width:{pct}%"></div></div>'
                f'<div class="progtext">{learned} of {n} points learned'
                f'{" - well done!" if n and learned == n else ""}</div>', unsafe_allow_html=True)
    for i, p in enumerate(r.points):
        c1, c2 = st.columns([0.07, 0.93], vertical_alignment="top")
        with c1:
            done = st.checkbox(f"Mark point {i + 1} as learned", key=f"got_{key}_{i}", label_visibility="collapsed")
        with c2:
            cites = [c for c in p["citations"] if c.verified]
            chip = f'<span class="chip">{esc(short_src(cites[0]))}</span>' if cites else ""
            st.markdown(f'<div class="card {"done" if done else ""}"><div class="stext">{esc(p["text"])}</div>{chip}</div>',
                        unsafe_allow_html=True)
            render_citations(p["citations"], f"{key}p{i}")


def render_result(r, key: str):
    label, cls = STATE_LOOK[r.state]
    st.markdown(f'<span class="badge {cls}">{label}</span>', unsafe_allow_html=True)
    if r.message:
        st.markdown(f'<div class="callout c-{cls}">{esc(r.message)}</div>', unsafe_allow_html=True)
    if r.conflict:
        st.markdown(f'<div class="callout c-b-warn"><b>The difference:</b> {esc(r.conflict["description"])}</div>', unsafe_allow_html=True)
    if r.answer:
        st.markdown(r.answer)
    if r.points:
        render_learning_map(r, key)
    if r.memory_aid:
        st.markdown('<div class="aidname">Memory aid: each letter is tied to a verified point above</div>', unsafe_allow_html=True)
        tiles = "".join(f'<div class="tile"><b>{esc(l["letter"])}</b><span>{esc(l["stands_for"])}</span><i>point {l["point_index"] + 1}</i></div>'
                        for l in r.memory_aid["letters"])
        st.markdown(f'<div class="aid">{tiles}</div>', unsafe_allow_html=True)
    for i, q in enumerate(r.quiz):
        st.markdown(f'<div class="qcard"><b>Question {i + 1}.</b> {esc(q["question"])}</div>', unsafe_allow_html=True)
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
st.title("Zimbabwe Nursing Tutor")
st.markdown('<p class="tagline">Learn from approved Zimbabwean guidelines. Every quote is checked, and it tells you when the sources do not cover your question.</p>',
            unsafe_allow_html=True)


def find_key() -> str:
    """Key from .env / environment, or Streamlit secrets (for a deployed app). Never shown in the UI."""
    k = runtime.get_key()
    if k:
        return k
    try:
        return str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:  # noqa: BLE001  (no secrets file)
        return ""


api_key = find_key()
if not api_key:
    # No key configured on the server: ask once, in the page. There is no sidebar in this app.
    st.markdown('<div class="notice"><b>One-time setup.</b> This tutor needs a Gemini API key. Paste it below; it is kept only in this browser session '
                'and is never saved or shown again. (Site owners: put it in <code>.env</code> to skip this step.)</div>', unsafe_allow_html=True)
    typed = st.text_input("Gemini API key", type="password", value=st.session_state.get("typed_key", ""), label_visibility="collapsed",
                          placeholder="Paste your Gemini API key")
    st.session_state["typed_key"] = typed.strip()
    api_key = typed.strip()
    if not api_key:
        st.stop()

try:
    tutor_obj = st.cache_resource(runtime.load_tutor, show_spinner="Loading the source index...")(api_key, True)
except runtime.SetupError as exc:
    st.markdown(f'<div class="callout c-b-bad">{esc(str(exc))}</div>', unsafe_allow_html=True)
    st.stop()
except legacy.TutorError as exc:
    st.markdown(f'<div class="callout c-b-bad">{esc(exc.user_message)}</div>', unsafe_allow_html=True)
    st.stop()

st.markdown(f'<div class="notice"><b>{esc(M.EDUCATION_NOTICE)}</b><small>{esc(M.PRIVACY_WARNING)}</small>'
            + ("" if tutor_obj.cfg.calibrated else f"<small>{esc(M.UNCALIBRATED)}</small>") + "</div>", unsafe_allow_html=True)

tab_ask, tab_browse, tab_bench, tab_src = st.tabs(["Ask the tutor", "Browse topics", "Tutor vs plain Gemini", "Sources"])

with tab_ask:
    ex = st.selectbox("Try an example (or type your own below)", [""] + EXAMPLES)
    q = st.text_area("Your study question", value=ex, height=90, max_chars=600, placeholder="e.g. What are the postnatal checks for a newborn?")
    st.markdown("**How should I teach it?**")
    if hasattr(st, "pills"):
        mode = st.pills("Teaching mode", list(MODES), default="explain", selection_mode="single",
                        format_func=lambda m: MODES[m][0], label_visibility="collapsed") or "explain"
    else:
        mode = st.radio("Teaching mode", list(MODES), format_func=lambda m: MODES[m][0], horizontal=True, label_visibility="collapsed")
    used = st.session_state.get("asked", 0)
    if st.button("Ask", type="primary"):
        if used >= MAX_QUESTIONS_PER_SESSION:
            st.markdown('<div class="callout c-b-warn">You have reached the question limit for this session (it protects the shared '
                        'Gemini quota). Refresh the page to start a new session.</div>', unsafe_allow_html=True)
            st.stop()
        st.session_state["asked"] = used + 1
        try:
            with st.spinner("Searching the sources and checking every quote..."):
                st.session_state["last"] = tutor_obj.ask(q, mode)
                st.session_state["rid"] = st.session_state.get("rid", 0) + 1  # new answer: fresh learning tracker
        except legacy.TutorError as exc:
            st.session_state["last"] = None
            st.markdown(f'<div class="callout c-b-bad">{esc(exc.user_message)}</div>', unsafe_allow_html=True)
            if exc.detail:
                with st.expander("Technical detail (for debugging)"):
                    st.code(str(exc.detail)[:600])
    r = st.session_state.get("last")
    if r:
        render_result(r, f"a{st.session_state.get('rid', 0)}")
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
                    st.session_state["brid"] = st.session_state.get("brid", 0) + 1
            except legacy.TutorError as exc:
                st.error(exc.user_message)
        if st.session_state.get("browse_r"):
            render_result(st.session_state["browse_r"], f"b{st.session_state.get('brid', 0)}")

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
    with st.expander("Settings"):
        tutor_obj.strict = st.toggle("Strict verification", value=tutor_obj.strict,
                                     help="On: if any quote or number fails the check, no answer is shown. Turn off only for testing.")
        st.caption("Needs an internet connection. Refreshing the page clears the current answer and your progress ticks.")
    seen = {}
    for c in tutor_obj.index.chunks:
        seen.setdefault(c.source_id, c)
    for sid, c in seen.items():
        n = sum(1 for x in tutor_obj.index.chunks if x.source_id == sid)
        st.markdown(f"**{c.document_title}**  \n{c.institution} - {c.edition or 'edition not stated'} - {c.publication_year or 'year not stated'} - "
                    f"{n} passages - currency: **{c.currency_status.replace('_', ' ')}** - reuse: {c.licence_or_reuse_status or 'not stated'}  \n{c.document_url}")
