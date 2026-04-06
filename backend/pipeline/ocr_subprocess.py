"""
OCR Worker — runs inside an isolated ProcessPoolExecutor worker process.

WHY A SEPARATE PROCESS:
  EasyOCR and Surya load large neural-network models and call into native C/C++
  extensions.  Any of these can segfault, be OOM-killed by the OS, or crash
  unpredictably — especially when interrupted mid-read (e.g. user refreshes the page).
  Running them in the same process as the FastAPI server means one OCR crash = full
  backend down.

  A ProcessPoolExecutor isolates the crash inside the worker process.  The main
  backend catches concurrent.futures.process.BrokenProcessPool, recreates the
  executor, and lets the user retry — without restarting the server.

RULES FOR FUNCTIONS IN THIS FILE:
  - Must be top-level (not lambdas, not closures) so pickle can serialise them.
  - Arguments and return values must be picklable (str, list, dataclasses — no
    open file handles, no asyncio objects).
  - Pass PDF paths as strings; return ExtractedReading dataclasses (picklable).
"""

import logging
import os
from pathlib import Path
from typing import List, Optional

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker-process lifecycle
# ---------------------------------------------------------------------------

def init_ocr_worker() -> None:
    """
    ProcessPoolExecutor initializer: called ONCE when the worker process starts.

    By default we do **not** load EasyOCR/Surya weights here: PyTorch allocates ~400MB+
    RAM at import/init, which fails on low-memory machines and looks like a broken
    backend even though /health and non-OCR APIs are fine.

    Set INSPECTION_REPORT_PRELOAD_OCR=1 to pre-load at worker start (faster first OCR;
    needs enough free RAM). Models still load lazily on first parse when preload is off.
    """
    try:
        preload = os.getenv("INSPECTION_REPORT_PRELOAD_OCR", "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        if not preload:
            _logger.info(
                "[ocr-worker] Model preload disabled (default). "
                "First inspection-report OCR may take longer. "
                "Set INSPECTION_REPORT_PRELOAD_OCR=1 if you have ~500MB+ free RAM and want warm-up."
            )
            return

        from backend.tml.inspection_report_parser import _get_easyocr_reader

        engine = os.getenv("INSPECTION_REPORT_STRUCTURED_OCR_ENGINE", "auto").strip().lower()
        if engine in ("auto", "easyocr", "tesseract", "surya"):
            _get_easyocr_reader()

        _logger.info("[ocr-worker] Models pre-loaded in worker process pid=%d", os.getpid())
    except Exception as exc:
        # Model load failures are reported per-request; don't crash the worker here.
        _logger.warning("[ocr-worker] Pre-load skipped: %s", exc)


def warmup_ocr_worker() -> bool:
    """
    Dummy job submitted at server startup to trigger worker-process creation and
    model pre-loading (via init_ocr_worker).  Returns True so the caller can
    confirm the worker is alive.
    """
    return True


# ---------------------------------------------------------------------------
# OCR task — the actual work submitted per request
# ---------------------------------------------------------------------------

def run_ocr_parse(pdf_path_strs: List[str], source_filenames: List[str]):
    """
    Parse one or more PDF files and return extracted readings.

    Runs entirely inside the isolated worker process.  All arguments and the
    return value are picklable (strings in, dataclasses out).

    Returns List[ExtractedReading].  Raises on unrecoverable error so the
    caller can propagate it as a BrokenProcessPool or plain exception.
    """
    from backend.tml.inspection_report_parser import parse_inspection_report_pdfs

    pdf_paths = [Path(p) for p in pdf_path_strs]
    return parse_inspection_report_pdfs(pdf_paths, source_filenames)
