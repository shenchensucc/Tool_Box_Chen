"""Debug LLM vision extraction - print raw response."""
import base64
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from openai import OpenAI
from backend.llm_config import get_api_key, get_chat_base_url
import pymupdf

pdf_path = Path("dev_tools/ground_truth_data/57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf")
doc = pymupdf.open(pdf_path)
images_b64 = []
for page in doc:
    pix = page.get_pixmap(dpi=150)
    images_b64.append(f"data:image/png;base64,{base64.b64encode(pix.tobytes(output='png')).decode()}")
doc.close()

prompt = """Extract UT thickness readings from the UT REPORT - Connections table.
Return JSON array: [{"circuit_id": "57-008V", "cml_id": "1.02-1", "min_reading": 0.358, "measurement_date": "2026-03-02"}]
Return ONLY valid JSON array."""
content = [{"type": "text", "text": prompt}]
for b64 in images_b64[:3]:
    content.append({"type": "image_url", "image_url": {"url": b64}})

client = OpenAI(base_url=get_chat_base_url(), api_key=get_api_key())
resp = client.chat.completions.create(
    model="gemini-3-flash-preview",
    messages=[{"role": "user", "content": content}],
    max_tokens=2000,
)
text = (resp.choices[0].message.content or "").strip()
print("Response length:", len(text))
print("Raw response:")
print(text)
if "```" in text:
    start = text.find("```json") + 7 if "```json" in text else text.find("```") + 3
    end = text.find("```", start)
    text = text[start:end] if end > start else text[start:]
text = re.sub(r",\s*([}\]])", r"\1", text)
try:
    data = json.loads(text)
    print("\nParsed:", json.dumps(data, indent=2))
except Exception as e:
    print("Parse error:", e)
