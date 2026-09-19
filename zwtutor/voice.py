"""Cartoon-style read-aloud. It ONLY reads text the pipeline already verified (never raw model output).

The voice is an original, bright, bouncy narrator style (not an imitation of any real character).
Primary: Gemini TTS preview (natural-language style prompt). Fallback: the browser's own speech synthesis
with raised pitch. Both are optional; the tutor works fully without sound.
"""
from __future__ import annotations

import html
import io
import json
import wave
from typing import Optional

from .models import State, TutorResult

TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"]  # preview names: re-check in Google's docs
VOICES = {"Puck (bouncy)": "Puck", "Leda (bright)": "Leda", "Zephyr (breezy)": "Zephyr", "Kore (calm)": "Kore"}
STYLE = ("Say the following the way a warm, upbeat friend and tutor would talk to one student, one to one: "
         "natural rhythm, small pauses between ideas, a smile in the voice, lively but clear and not too fast. "
         "Do not sound like you are reading a document. Do not add, remove or change any word: ")
MAX_CHARS = 700


def speakable_text(r: TutorResult) -> str:
    """Only verified content or fixed app messages. Numbers and units are read exactly as printed."""
    if r.state == State.GROUNDED or r.state == State.CONFLICTING_SOURCES:
        parts = []
        if r.answer:
            parts.append(r.answer.split("\n\n")[0])
        parts += [p["text"] for p in r.points if p.get("verified")]
        if r.memory_aid:
            parts.append("Memory aid: " + r.memory_aid["text"] + ". " + ". ".join(
                f"{l['letter']} for {l['stands_for']}" for l in r.memory_aid["letters"]))
        text = " ".join(parts)
    else:
        text = r.message
    return text[:MAX_CHARS * 3]


# Fixed conversational wrapper phrases. They contain NO clinical content: every fact spoken comes from
# a verified point, and the wording of those points is left exactly as verified.
_OPEN = ["Okay, good question! Here is what the guidelines say.", "Right, let's go through this together.",
         "Great, I looked it up in the Zimbabwe guidelines for you.", "Alright, here's what I found."]
_NEXT = ["First,", "Then,", "Next,", "After that,", "Also,", "And,"]
_LAST = "And finally,"
_CLOSE = ["Does that make sense? You can ask me to quiz you on it.", "Want to test yourself? Pick Quiz me, and I'll ask you some questions.",
          "That's the main idea. Ask me another question whenever you're ready."]
_REFUSAL_LEAD = {
    State.NOT_IN_CORPUS: "Hmm, I looked through my Zimbabwe guidelines, and I can't find that. ",
    State.CANNOT_VERIFY: "Hmm, I found something close, but I couldn't check it properly. ",
    State.CONFLICTING_SOURCES: "Interesting, the sources don't fully agree here. ",
    State.OUT_OF_SCOPE: "I'm sorry, I can't help with that one. ",
    State.EMERGENCY: "Please stop, this sounds urgent. ",
    State.PRIVACY_BLOCKED: "Careful, please don't share personal details. ",
    State.NEEDS_CLARIFICATION: "I'd love to help, but I need a bit more. ",
}


def _pick(options: list, seed: str):
    return options[sum(ord(c) for c in seed) % len(options)]


def _source_phrase(p: dict) -> str:
    cites = [c for c in p.get("citations", []) if getattr(c, "verified", False)]
    if not cites:
        return ""
    ch = cites[0].chunk
    where = f", page {ch.page_number}" if ch.page_number else ""
    return f"That's from the {ch.document_title}{where}."


def speech_script(r: TutorResult, with_sources: bool = True) -> str:
    """Conversational spoken version of a result. Only verified points and fixed phrases; nothing else."""
    if r.state not in (State.GROUNDED, State.CONFLICTING_SOURCES):
        return (_REFUSAL_LEAD.get(r.state, "") + (r.message or "")).strip()[:MAX_CHARS * 3]
    seed = (r.points[0]["text"] if r.points else r.answer) or "x"
    out = [_pick(_OPEN, seed)]
    if r.answer:
        out.append(r.answer.split("\n\n")[0])
    pts = [p for p in r.points if p.get("verified")]
    last_src = None
    for i, p in enumerate(pts):
        lead = _LAST if (i == len(pts) - 1 and len(pts) > 1) else _NEXT[i % len(_NEXT)] if i else "First,"
        text = p["text"].strip()
        out.append(f"{lead} {text}")
        if with_sources:  # say the source once, then again only if the document changes
            sp = _source_phrase(p)
            if sp and sp != last_src:
                out.append(sp if last_src is None else sp.replace("That's from", "This one is from"))
                last_src = sp
    if r.memory_aid:
        out.append("Here's a trick to help you remember. " + r.memory_aid["text"] + ". " + ". ".join(
            f"{l['letter']} is for {l['stands_for']}" for l in r.memory_aid["letters"]) + ".")
    for i, q in enumerate(r.quiz):
        opts = q.get("options") or []
        out.append(f"Question {i + 1}. {q['question']} " + " ".join(f"Option {chr(65 + j)}, {o}." for j, o in enumerate(opts)))
        out.append(f"The answer is: {q['answer']}. {q.get('explanation', '')}".strip())
    for i, c in enumerate(r.cards):
        out.append(f"Card {i + 1}. {c['front']}. The answer is: {c['back']}.")
    out.append(_pick(_CLOSE, seed))
    return " ".join(x.strip() for x in out if x and x.strip())[:MAX_CHARS * 6]


def pcm_to_wav(pcm: bytes, rate: int = 24000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def _split(text: str, n: int = MAX_CHARS) -> list[str]:
    out, cur = [], ""
    for sent in text.replace("\n", " ").split(". "):
        s = sent.strip()
        if not s:
            continue
        s = s if s.endswith(".") else s + "."
        if len(cur) + len(s) + 1 > n and cur:
            out.append(cur)
            cur = ""
        cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def gemini_tts(text: str, voice: str = "Puck", api_key: Optional[str] = None, client=None) -> bytes:
    """Returns WAV bytes. Raises on any failure so the caller can fall back to the browser voice."""
    from google import genai
    from google.genai import types
    c = client or genai.Client(api_key=api_key)
    pcm = b""
    last: Optional[Exception] = None
    for model in TTS_MODELS:
        try:
            pcm = b""
            for part in _split(text):
                r = c.models.generate_content(
                    model=model, contents=STYLE + part,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
                pcm += r.candidates[0].content.parts[0].inline_data.data
            if pcm:
                return pcm_to_wav(pcm)
        except Exception as exc:  # noqa: BLE001
            last = exc
    raise RuntimeError(f"Gemini voice unavailable: {last}")


def browser_voice_html(text: str, pitch: float = 1.7, rate: float = 1.05) -> str:
    """A button that reads the text with the browser's speech synthesis (no API, no key)."""
    t = json.dumps(text).replace("</", "<\\/").replace("<!--", "<\\!--")
    return f"""<button id="b" style="font-size:16px;padding:8px 14px;border-radius:20px;border:2px solid #f5a623;background:#fff3d6;cursor:pointer">
&#128266; Read aloud (browser voice)</button>
<script>
const b=document.getElementById('b');
b.onclick=()=>{{const s=window.speechSynthesis;if(!s){{b.textContent='No browser voice here';return;}}
if(s.speaking){{s.cancel();return;}}
const u=new SpeechSynthesisUtterance({t});u.pitch={pitch};u.rate={rate};s.speak(u);}};
</script>"""
