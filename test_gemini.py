"""Tiny one-request Gemini test (guide section 11).

Run this BEFORE debugging the Streamlit app: if this works, your Python, venv, SDK
and API key are fine, and any later problem is in the app.

    python test_gemini.py
"""
import os
import sys

from dotenv import load_dotenv
from google import genai

import tutor

load_dotenv()

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")

client = genai.Client()  # reads GEMINI_API_KEY from the environment
try:
    response = client.models.generate_content(
        model=tutor.model_name(),
        contents="Explain AI governance in one simple sentence.",
    )
except Exception as exc:  # noqa: BLE001
    err = tutor.translate_exception(exc)
    sys.exit(f"FAILED ({err.kind}): {err.user_message}\n  {err.detail[:300]}")

print(f"Model: {tutor.model_name()}")
print(response.text)
