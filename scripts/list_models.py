"""Show which Gemini models YOUR key can use for answers, and which for embeddings.

    python scripts/list_models.py

Then set GEMINI_MODEL=<one of the names printed> in .env.
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
    sys.exit("Put your key in .env first.")
from google import genai  # noqa: E402

from zwtutor.generate import discover_models  # noqa: E402

c = genai.Client(api_key=key)
print("Text models this key can use (best first):")
for n in discover_models(c):
    print("  ", n)
print("\nEmbedding models:")
for m in c.models.list():
    if "embed" in (m.name or ""):
        print("  ", m.name.replace("models/", ""))
print("\nPut one of the text models in .env, e.g.  GEMINI_MODEL=<name>")
