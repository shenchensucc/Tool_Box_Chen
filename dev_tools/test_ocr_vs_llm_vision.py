"""
Compare local OCR vs LLM Vision extraction on 57-008V report.

Run: python dev_tools/test_ocr_vs_llm_vision.py
     python dev_tools/test_ocr_vs_llm_vision.py --llm-only   # Skip OCR (faster)

Requires: AI_BUILDER_TOKEN for LLM tests.
Uses ground truth expected values to score each method.
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env for AI_BUILDER_TOKEN
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

GROUND_TRUTH = ROOT / "dev_tools" / "ground_truth_data"
PDF_NAME = "57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026.pdf"
GT_JSON = "57-008V 1-1 CML 1.02, 11.03 UT-AUTNAR-26-33-03.02.2026_ground_truth.json"
TOLERANCE = 0.01


def load_expected() -> dict:
    """Load expected (circuit, cml) -> reading from ground truth."""
    gt_path = GROUND_TRUTH / GT_JSON
    if not gt_path.exists():
        return {}
    with open(gt_path, encoding="utf-8") as f:
        gt = json.load(f)
    expected = {}
    for r in gt.get("readings", []):
        if r.get("is_correct"):
            key = (r["circuit_id"], r["cml_id"])
            expected[key] = r.get("expected_reading") or r["min_reading"]
    for a in gt.get("additions", []):
        key = (a["circuit_id"], a["cml_id"])
        expected[key] = a["min_reading"]
    return expected


def score_results(results: list, expected: dict) -> tuple[int, int, list]:
    """Return (passed, total, errors)."""
    got = {(r.circuit_id, r.cml_id): r.min_reading for r in results}
    passed = 0
    errors = []
    for (circ, cml), exp in expected.items():
        if (circ, cml) not in got:
            errors.append(f"Missing {circ} {cml} (expected {exp})")
        elif abs(got[(circ, cml)] - exp) <= TOLERANCE:
            passed += 1
        else:
            errors.append(f"{circ} {cml}: got {got[(circ, cml)]}, expected {exp}")
    return passed, len(expected), errors


def run_ocr(pdf_path: Path, tesseract_only: bool = False, high_dpi: bool = False, preprocess: bool = False) -> list:
    """OCR-only extraction (LLM disabled)."""
    from backend.tml.inspection_report_parser import parse_inspection_report_pdf

    old_llm = os.environ.pop("INSPECTION_REPORT_LLM_VISION", None)
    if tesseract_only:
        os.environ["INSPECTION_REPORT_OCR_ENGINE"] = "tesseract"
    if high_dpi:
        os.environ["INSPECTION_REPORT_OCR_HIGH_DPI"] = "1"
    if preprocess:
        os.environ["INSPECTION_REPORT_OCR_PREPROCESS"] = "1"
    try:
        return parse_inspection_report_pdf(pdf_path, PDF_NAME)
    finally:
        os.environ.pop("INSPECTION_REPORT_OCR_ENGINE", None)
        os.environ.pop("INSPECTION_REPORT_OCR_HIGH_DPI", None)
        os.environ.pop("INSPECTION_REPORT_OCR_PREPROCESS", None)
        if old_llm is not None:
            os.environ["INSPECTION_REPORT_LLM_VISION"] = old_llm


def run_llm_vision(pdf_path: Path, model: str) -> list:
    """LLM Vision extraction via full parser (OCR-like text → zone assignment)."""
    from backend.tml.inspection_report_parser import parse_inspection_report_pdf

    os.environ["INSPECTION_REPORT_LLM_VISION"] = "1"
    os.environ["INSPECTION_REPORT_LLM_ONLY"] = "1"
    os.environ["INSPECTION_REPORT_VISION_MODEL"] = model
    try:
        return parse_inspection_report_pdf(pdf_path, PDF_NAME)
    finally:
        os.environ.pop("INSPECTION_REPORT_LLM_VISION", None)
        os.environ.pop("INSPECTION_REPORT_LLM_ONLY", None)
        os.environ.pop("INSPECTION_REPORT_VISION_MODEL", None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-only", action="store_true", help="Skip OCR test (faster)")
    parser.add_argument("--tesseract-only", action="store_true", help="Use Tesseract only (skip EasyOCR, faster)")
    parser.add_argument("--high-dpi", action="store_true", help="Use 400 DPI for OCR (slower, may improve accuracy)")
    parser.add_argument("--preprocess", action="store_true", help="Apply contrast+sharpen before OCR")
    args = parser.parse_args()

    pdf_path = GROUND_TRUTH / PDF_NAME
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        return 1

    expected = load_expected()
    if not expected:
        print("No expected values in ground truth")
        return 1

    print("=" * 60)
    print("OCR vs LLM Vision Comparison - 57-008V Report")
    print("=" * 60)
    print(f"Expected: {expected}")
    print()

    scores = []

    # 1. OCR (EasyOCR + Tesseract)
    if not args.llm_only:
        eng = "Tesseract only" if args.tesseract_only else "EasyOCR primary, Tesseract fallback"
        print(f"1. OCR ({eng})...")
        try:
            ocr_results = run_ocr(
                pdf_path,
                tesseract_only=args.tesseract_only,
                high_dpi=args.high_dpi,
                preprocess=args.preprocess,
            )
            passed, total, errors = score_results(ocr_results, expected)
            scores.append(("OCR", passed, total, errors, ocr_results))
            print(f"   Passed: {passed}/{total}")
            for r in ocr_results:
                print(f"   {r.cml_id}: {r.min_reading}")
            if errors:
                for e in errors[:5]:
                    print(f"   ! {e}")
        except Exception as ex:
            print(f"   ERROR: {ex}")
            scores.append(("OCR", 0, len(expected), [str(ex)], []))

    # 2. GPT-5
    if os.getenv("AI_BUILDER_TOKEN"):
        print("\n2. LLM Vision (gpt-5)...")
        try:
            gpt5_results = run_llm_vision(pdf_path, "gpt-5")
            passed, total, errors = score_results(gpt5_results, expected)
            scores.append(("gpt-5", passed, total, errors, gpt5_results))
            print(f"   Passed: {passed}/{total}")
            for r in gpt5_results:
                print(f"   {r.cml_id}: {r.min_reading}")
            if errors:
                for e in errors[:5]:
                    print(f"   ! {e}")
        except Exception as ex:
            print(f"   ERROR: {ex}")
            scores.append(("gpt-5", 0, len(expected), [str(ex)], []))
    else:
        print("\n2. LLM Vision (gpt-5): SKIP (no AI_BUILDER_TOKEN)")

    # 3. Gemini Flash
    if os.getenv("AI_BUILDER_TOKEN"):
        print("\n3. LLM Vision (gemini-3-flash-preview)...")
        try:
            gemini_results = run_llm_vision(pdf_path, "gemini-3-flash-preview")
            passed, total, errors = score_results(gemini_results, expected)
            scores.append(("gemini-3-flash", passed, total, errors, gemini_results))
            print(f"   Passed: {passed}/{total}")
            for r in gemini_results:
                print(f"   {r.cml_id}: {r.min_reading}")
            if errors:
                for e in errors[:5]:
                    print(f"   ! {e}")
        except Exception as ex:
            print(f"   ERROR: {ex}")
            scores.append(("gemini-3-flash", 0, len(expected), [str(ex)], []))
    else:
        print("\n3. LLM Vision (gemini-3-flash): SKIP (no AI_BUILDER_TOKEN)")

    # 4. Gemini 2.5 Pro (more accurate)
    if os.getenv("AI_BUILDER_TOKEN"):
        print("\n4. LLM Vision (gemini-2.5-pro)...")
        try:
            gemini_pro_results = run_llm_vision(pdf_path, "gemini-2.5-pro")
            passed, total, errors = score_results(gemini_pro_results, expected)
            scores.append(("gemini-2.5-pro", passed, total, errors, gemini_pro_results))
            print(f"   Passed: {passed}/{total}")
            for r in gemini_pro_results:
                print(f"   {r.cml_id}: {r.min_reading}")
            if errors:
                for e in errors[:5]:
                    print(f"   ! {e}")
        except Exception as ex:
            print(f"   ERROR: {ex}")
            scores.append(("gemini-2.5-pro", 0, len(expected), [str(ex)], []))
    else:
        print("\n4. LLM Vision (gemini-2.5-pro): SKIP (no AI_BUILDER_TOKEN)")

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    if not scores:
        print("  No results")
        return 0
    best = max(scores, key=lambda s: s[1])
    for name, passed, total, errors, _ in scores:
        pct = 100 * passed / total if total else 0
        marker = " <-- BEST" if (name, passed) == (best[0], best[1]) else ""
        print(f"  {name}: {passed}/{total} ({pct:.0f}%){marker}")

    # Use best LLM result to inform OCR improvements
    llm_scores = [(n, p, t, e, r) for n, p, t, e, r in scores if "gemini" in n or "gpt" in n]
    ocr_scores = [(n, p, t, e, r) for n, p, t, e, r in scores if n == "OCR"]
    if llm_scores and ocr_scores:
        best_llm = max(llm_scores, key=lambda s: s[1])
        ocr_passed = ocr_scores[0][1]
        if best_llm[1] > ocr_passed:
            print(f"\nLLM ({best_llm[0]}) outperformed OCR ({best_llm[1]} vs {ocr_passed}). Consider using as fallback.")
            print("Reference values from best LLM for OCR tuning:")
            for r in best_llm[4]:
                print(f"  {r.cml_id}: {r.min_reading}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
