"""
Minimal test: Does AI_BUILDER_TOKEN work with the AI Builders API?
Uses a tiny text-only request (no vision) for fast feedback.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

def main():
    token = os.getenv("AI_BUILDER_TOKEN", "")
    if not token:
        print("FAIL: AI_BUILDER_TOKEN not set")
        return 1

    from backend.llm_config import get_chat_base_url, get_api_key
    from openai import OpenAI

    print("Testing API connection (text-only, no vision)...")
    client = OpenAI(base_url=get_chat_base_url(), api_key=get_api_key())
    try:
        resp = client.chat.completions.create(
            model="grok-4-fast",
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            max_tokens=10,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"OK: API responded: {content[:50]}")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
