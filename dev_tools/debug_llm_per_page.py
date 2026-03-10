"""Debug LLM vision - one call per page."""
import base64
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from openai import OpenAI
from backend.llm_config import get_api_key, get_chat_base_url
import pymupdf

pdf_path = ROOT / "dev_tools/ground_truth_data/57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf"
doc = pymupdf.open(pdf_path)

prompt = """Extract thickness readings from tables. Return compact JSON:
[{"circuit_id":"57-008V","cml_id":"1.02-1","min_reading":0.358,"measurement_date":"2026-03-02"}]
If no table, return []."""

client = OpenAI(base_url=get_chat_base_url(), api_key=get_api_key())
for page_idx in range(len(doc)):
    pix = doc[page_idx].get_pixmap(dpi=150)
    b64 = f"data:image/png;base64,{base64.b64encode(pix.tobytes(output='png')).decode()}"
    content = [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": b64}}]
    try:
        resp = client.chat.completions.create(
            model="gemini-3-flash-preview",
            messages=[{"role": "user", "content": content}],
            max_tokens=1000,
        )
        text = (resp.choices[0].message.content or "").strip()
        if page_idx in (2, 3, 4) and text:
            print(f"  Raw ({len(text)} chars): {repr(text[:600])}")
        if "```" in text:
            start = text.find("```json") + 7 if "```json" in text else text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end] if end > start else text[start:]
        text = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            data = json.loads(text) if text else []
        except json.JSONDecodeError as e:
            print(f"  JSON error: {e}")
            data = []
        n = len(data) if isinstance(data, list) else 0
        print(f"Page {page_idx}: {n} readings")
        if data:
            print(f"  {json.dumps(data)}")
    except Exception as e:
        print(f"Page {page_idx}: ERROR {e}")
doc.close()
