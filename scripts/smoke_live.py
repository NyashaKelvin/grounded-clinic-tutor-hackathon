"""Live smoke test of the three Gemini features this app depends on. Run FIRST, before building the index.

    python scripts/smoke_live.py

Each step prints PASS/FAIL with the real error, so you know which model name or setting to fix.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
key = os.getenv("GEMINI_API_KEY", "").strip()
if not key or "replace_with" in key:
    sys.exit("Put your key in .env (GEMINI_API_KEY=...) first.")

ok = True


def step(name, fn):
    global ok
    try:
        print(f"[PASS] {name}: {fn()}")
    except Exception as exc:  # noqa: BLE001
        ok = False
        print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")


def embed():
    from zwtutor.embed import GeminiEmbedder
    e = GeminiEmbedder(api_key=key, sleep=lambda s: None)
    v = e.embed_documents(["Hand hygiene reduces infection.", "Newborn danger signs."])
    q = e.embed_query("how to prevent infection")
    return f"{v.shape}, cosine(query, doc0)={float(v[0] @ q):.2f}, cosine(query, doc1)={float(v[1] @ q):.2f}"


def generate():
    from zwtutor.generate import GeminiGenerator, build_prompt
    from zwtutor.models import Chunk, Hit
    from zwtutor.schema import build_schema
    c = Chunk("T", "Test", "Test doc", "1st", "2099", "Sec", "1", 1, "", "", "", "T:p1:0",
              "Wash hands with soap and water for at least 20 seconds before touching a patient.")
    h = Hit(c, 0.9, 1.0, 1.0, 1.0)
    d, model = GeminiGenerator(api_key=key).generate(build_prompt("How long should hands be washed?", "explain", [h]), build_schema("explain", ["T:p1:0"]))
    return f"model={model}, points={len(d.get('points', []))}, cannot_answer={d.get('cannot_answer')}"


def tts():
    from zwtutor.voice import gemini_tts
    wav = gemini_tts("Hello, student nurse! Let's learn something together.", "Puck", api_key=key)
    return f"{len(wav)} bytes of WAV"


step("Embeddings (gemini-embedding-001)", embed)
step("Structured generation with JSON schema", generate)
step("Text-to-speech (preview model; failure here is OK, the app falls back to the browser voice)", tts)
sys.exit(0 if ok else 1)
