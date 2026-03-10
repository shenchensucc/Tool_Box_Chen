"""
Debug: Print raw LLM Vision response to diagnose parsing issues.
"""
import base64
import json
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
    pdf_path = ROOT / "dev_tools" / "ground_truth_data" / "57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf"
    import pymupdf
    from backend.llm_config import get_chat_base_url, get_api_key
    from openai import OpenAI

    doc = pymupdf.open(pdf_path)
    images_b64 = []
    for i, page in enumerate(doc):
        if i >= 3:  # Only first 3 pages for faster test
            break
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes(output="png")
        images_b64.append(f"data:image/png;base64,{base64.b64encode(img_bytes).decode()}")
    doc.close()

    prompt = """Extract UT thickness readings from this inspection report PDF.
Return a JSON array: [{"circuit_id": "57-008V", "cml_id": "1.02-1", "min_reading": 0.358, "measurement_date": "2026-03-02"}].
Return ONLY valid JSON array, no other text."""

    content = [{"type": "text", "text": prompt}]
    for b64 in images_b64:
        content.append({"type": "image_url", "image_url": {"url": b64}})

    model = os.getenv("INSPECTION_REPORT_VISION_MODEL", "gemini-3-flash-preview")
    print(f"Calling {model} with 3 pages...")
    client = OpenAI(base_url=get_chat_base_url(), api_key=get_api_key())
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=2000,
    )
    text = (resp.choices[0].message.content or "").strip()
    print("--- RAW RESPONSE ---")
    print(text[:2000])
    if len(text) > 2000:
        print("... (truncated)")
    print("--- END ---")

    # Try to parse
    if "```" in text:
        start = text.find("```json") + 7 if "```json" in text else text.find("```") + 3
        end = text.find("```", start)
        text = text[start:end] if end > start else text[start:]
    try:
        data = json.loads(text)
        print(f"Parsed: {len(data) if isinstance(data, list) else 'not a list'} items")
    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")

if __name__ == "__main__":
    main()
