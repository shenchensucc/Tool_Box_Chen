"""
Quick test: Is the LLM Vision API for inspection reports working?
Prints result or error. Uses 1-page PDF to minimize latency.
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
    print("Checking env...")
    token = os.getenv("AI_BUILDER_TOKEN", "")
    llm_vision = os.getenv("INSPECTION_REPORT_LLM_VISION", "")
    if not token:
        print("FAIL: AI_BUILDER_TOKEN not set in .env")
        return 1
    if not llm_vision:
        print("WARN: INSPECTION_REPORT_LLM_VISION not set (will set for this test)")
        os.environ["INSPECTION_REPORT_LLM_VISION"] = "1"

    pdf_path = ROOT / "dev_tools" / "ground_truth_data" / "57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf"
    if not pdf_path.exists():
        print(f"FAIL: PDF not found: {pdf_path}")
        return 1

    model = os.getenv("INSPECTION_REPORT_VISION_MODEL", "gemini-3-flash-preview")
    print(f"Calling LLM Vision API ({model})...")
    sys.stdout.flush()
    sys.stderr.flush()

    try:
        from backend.tml.inspection_report_parser import parse_inspection_report_pdf
        os.environ["INSPECTION_REPORT_LLM_VISION"] = "1"
        os.environ["INSPECTION_REPORT_OCR_ENGINE"] = "tesseract"
        results = parse_inspection_report_pdf(pdf_path, pdf_path.name)
        if results:
            print(f"OK: Got {len(results)} readings")
            for r in results[:5]:
                print(f"  {r.cml_id}: {r.min_reading}")
            if len(results) > 5:
                print(f"  ... and {len(results) - 5} more")
        else:
            print("FAIL: No results returned")
        return 0 if results else 1
    except Exception as e:
        print(f"FAIL: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        os.environ.pop("INSPECTION_REPORT_OCR_ENGINE", None)

if __name__ == "__main__":
    sys.exit(main())
