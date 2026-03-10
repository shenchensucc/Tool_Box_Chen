"""
Minimal vision test: Does kimi-k2.5 vision work?
Sends 1 small image (single PDF page) to minimize latency.
"""
import base64
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

    pdf_path = ROOT / "dev_tools" / "ground_truth_data" / "57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf"
    if not pdf_path.exists():
        print("FAIL: PDF not found")
        return 1

    # Render only first page
    import pymupdf
    doc = pymupdf.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap(dpi=150)  # Lower DPI = smaller payload
    img_bytes = pix.tobytes(output="png")
    doc.close()
    b64 = f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}"
    size_kb = len(img_bytes) // 1024
    print(f"Sending 1 page (~{size_kb} KB) to kimi-k2.5...")

    from backend.llm_config import get_chat_base_url, get_api_key
    from openai import OpenAI

    client = OpenAI(base_url=get_chat_base_url(), api_key=get_api_key())
    try:
        resp = client.chat.completions.create(
            model="kimi-k2.5",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "What text do you see? Reply in one short sentence."},
                    {"type": "image_url", "image_url": {"url": b64}},
                ],
            }],
            max_tokens=100,
        )
        content = (resp.choices[0].message.content or "").strip()
        print(f"OK: Vision API responded: {content[:200]}...")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
