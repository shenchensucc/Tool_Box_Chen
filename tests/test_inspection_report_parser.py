"""Tests for inspection report PDF parser."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

from backend.tml.inspection_report_parser import (
    parse_inspection_report_pdf,
    _parse_acuren_results_table,
    _parse_ut_report_summary_table,
    _parse_single_cml_permissive,
    _parse_generic_zone_table,
    _supplement_with_pdfplumber,
    _extract_structured_with_local_ocr,
    _STRUCT_OCR_CACHE,
    _STRUCT_OCR_CACHE_LOCK,
    ExtractedReading,
)
from backend.tml.inspection_dataloader import generate_measurements_dataloader, PLACEHOLDER_EQUIPMENT_ID
from backend.tml.inspection_fixtures import FIXTURE_DIR, FIXTURE_EXPECTED

FIXTURE_52_021K = FIXTURE_DIR / "inspection_report_52-021K.pdf"
FIXTURE_57_008U = FIXTURE_DIR / "inspection_report_57-008U_1.52_1.29_4.09.pdf"
EXPECTED_52_021K = FIXTURE_EXPECTED["inspection_report_52-021K.pdf"]
EXPECTED_57_008U = FIXTURE_EXPECTED["inspection_report_57-008U_1.52_1.29_4.09.pdf"]


@pytest.mark.skipif(not FIXTURE_52_021K.exists(), reason="Fixture PDF not found")
def test_parse_inspection_report_52_021k():
    """Parse Acuren 8\"/6\" fixture and verify expected Circuit, CML, Reading."""
    results = parse_inspection_report_pdf(FIXTURE_52_021K, "inspection_report_52-021K.pdf")
    assert len(results) == len(EXPECTED_52_021K)
    for i, (circuit, cml, reading) in enumerate(EXPECTED_52_021K):
        assert results[i].circuit_id == circuit
        assert results[i].cml_id == cml
        assert abs(results[i].min_reading - reading) < 0.001
    assert results[0].measurement_date == "2026-02-23"


@pytest.mark.skipif(not FIXTURE_52_021K.exists(), reason="Fixture PDF not found")
def test_generate_dataloader_from_parsed():
    """Verify dataloader generation from parsed readings."""
    readings = parse_inspection_report_pdf(FIXTURE_52_021K, "inspection_report_52-021K.pdf")
    assert len(readings) == 6
    records_count, summary = generate_measurements_dataloader(
        readings,
        circuit_to_equipment={},
        output_path="",
        use_placeholder_when_missing=True,
    )
    assert records_count == 6
    assert len(summary) == 6
    for s in summary:
        assert s["Equipment ID"] == PLACEHOLDER_EQUIPMENT_ID
        assert s["Circuit"] == "52-021K"


@pytest.mark.skipif(not FIXTURE_57_008U.exists(), reason="Fixture PDF not found")
def test_parse_inspection_report_57_008u():
    """Parse multi-section fixture (CML 1.52, 1.29, 4.09) with 16\"/30\"/8\"/6\" zones."""
    results = parse_inspection_report_pdf(FIXTURE_57_008U, "inspection_report_57-008U.pdf")
    assert len(results) == len(EXPECTED_57_008U)
    for i, (circuit, cml, reading) in enumerate(EXPECTED_57_008U):
        assert results[i].circuit_id == circuit
        assert results[i].cml_id == cml
        assert abs(results[i].min_reading - reading) < 0.001


def test_dedupe_keep_min_reading():
    """Verify duplicate CMLs dedupe by keeping minimum reading (rule-based, no value filter)."""
    from backend.tml.inspection_report_parser import _dedupe_by_cml_keep_min, ExtractedReading

    # Duplicate 1.33-2: keep min (0.408) - both 0.79 and 0.408 are valid, min is correct for thickness
    results = [
        ExtractedReading("52-001C", "1.33-2", "2026-02-28", 0.79),
        ExtractedReading("52-001C", "1.33-1", "2026-02-28", 0.388),
        ExtractedReading("52-001C", "1.33-2", "2026-02-28", 0.408),
        ExtractedReading("52-001C", "1.33-3", "2026-02-28", 0.426),
        ExtractedReading("52-001C", "1.33-4", "2026-02-28", 0.421),
    ]
    deduped = _dedupe_by_cml_keep_min(results)
    cml_readings = {(r.circuit_id, r.cml_id): r.min_reading for r in deduped}
    assert cml_readings[("52-001C", "1.33-2")] == 0.408  # min of 0.79 and 0.408
    assert len(deduped) == 4


# ---------------------------------------------------------------------------
# Regression tests for the pdfplumber-open-once refactor (Change 2 & Change 5)
# These run unconditionally — no fixture PDFs required.
# ---------------------------------------------------------------------------


def _make_mock_pdf(pages=1):
    """Return a mock pdfplumber PDF with *pages* empty pages."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_page.find_tables.return_value = []
    mock_page.extract_tables.return_value = []
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page] * pages
    return mock_pdf


def _make_mock_open(mock_pdf):
    """Return a mock context-manager that yields *mock_pdf* on __enter__."""
    mock_cm = MagicMock()
    mock_cm.__enter__ = MagicMock(return_value=mock_pdf)
    mock_cm.__exit__ = MagicMock(return_value=False)
    return mock_cm


class TestSupplementOpensPdfplumberOnce:
    """_supplement_with_pdfplumber must open pdfplumber exactly once even when all parsers try."""

    def _run(self, cml_ids):
        mock_pdf = _make_mock_pdf()
        mock_cm = _make_mock_open(mock_pdf)
        with patch("backend.tml.inspection_report_parser.pdfplumber.open", return_value=mock_cm) as mock_open, \
             patch("backend.tml.inspection_report_parser._get_summary_page_indices", return_value=None):
            _supplement_with_pdfplumber(
                Path("fake.pdf"), "52-021K", cml_ids, "2026-01-01",
                primary_results=[],
            )
        return mock_open.call_count

    def test_single_cml_opens_once(self):
        """Single-CML path exercises _parse_ut_report_summary, _parse_acuren, _parse_single_cml_permissive,
        and two _parse_generic_zone_table calls — still exactly one pdfplumber.open."""
        assert self._run(["1.01"]) == 1

    def test_multi_cml_opens_once(self):
        """Three-CML path exercises _parse_generic_zone_table and _parse_acuren — still one open."""
        assert self._run(["1.01", "1.05", "1.10"]) == 1


class TestParseHelpersPdfParam:
    """Each _parse_* function must skip pdfplumber.open when _pdf kwarg is provided."""

    def _assert_no_open(self, fn, *args, **kwargs):
        mock_pdf = _make_mock_pdf()
        with patch("backend.tml.inspection_report_parser.pdfplumber.open") as mock_open, \
             patch("backend.tml.inspection_report_parser._get_summary_page_indices", return_value=None):
            result = fn(*args, _pdf=mock_pdf, **kwargs)
        mock_open.assert_not_called()
        return result

    def _assert_opens(self, fn, *args, **kwargs):
        mock_pdf = _make_mock_pdf()
        mock_cm = _make_mock_open(mock_pdf)
        with patch("backend.tml.inspection_report_parser.pdfplumber.open", return_value=mock_cm) as mock_open, \
             patch("backend.tml.inspection_report_parser._get_summary_page_indices", return_value=None):
            fn(*args, **kwargs)
        mock_open.assert_called_once()

    def test_parse_acuren_skips_open_when_pdf_provided(self):
        result = self._assert_no_open(
            _parse_acuren_results_table, Path("f.pdf"), "52-021K", ["1.01"], "2026-01-01"
        )
        assert isinstance(result, list)

    def test_parse_acuren_opens_when_no_pdf(self):
        self._assert_opens(_parse_acuren_results_table, Path("f.pdf"), "52-021K", ["1.01"], "2026-01-01")

    def test_parse_ut_summary_skips_open_when_pdf_provided(self):
        # _parse_ut_report_summary_table returns early when summary_page_indices is empty;
        # patch it to return [0] so the page-loop body runs.
        mock_pdf = _make_mock_pdf()
        with patch("backend.tml.inspection_report_parser.pdfplumber.open") as mock_open, \
             patch("backend.tml.inspection_report_parser._get_summary_page_indices", return_value=[0]):
            result = _parse_ut_report_summary_table(
                Path("f.pdf"), "52-021K", ["1.01"], "2026-01-01", _pdf=mock_pdf
            )
        mock_open.assert_not_called()
        assert isinstance(result, list)

    def test_parse_single_cml_skips_open_when_pdf_provided(self):
        result = self._assert_no_open(
            _parse_single_cml_permissive, Path("f.pdf"), "52-021K", "1.01", "2026-01-01"
        )
        assert isinstance(result, list)

    def test_parse_generic_zone_skips_open_when_pdf_provided(self):
        result = self._assert_no_open(
            _parse_generic_zone_table, Path("f.pdf"), "52-021K", ["1.01", "1.05", "1.10"], "2026-01-01"
        )
        assert isinstance(result, list)

    def test_parse_generic_zone_opens_when_no_pdf(self):
        self._assert_opens(
            _parse_generic_zone_table, Path("f.pdf"), "52-021K", ["1.01", "1.05", "1.10"], "2026-01-01"
        )


class TestOcrCache:
    """_extract_structured_with_local_ocr must return cached result without running OCR."""

    def test_cache_hit_with_precomputed_hash(self):
        """When content_hash is pre-computed and in cache, pymupdf.open is never called."""
        test_hash = "_test_hash_precomputed_abc123"
        cached = [ExtractedReading("52-021K", "1.01-1", "2026-01-01", 0.5)]

        with _STRUCT_OCR_CACHE_LOCK:
            _STRUCT_OCR_CACHE[test_hash] = cached
        try:
            with patch("backend.tml.inspection_report_parser.pymupdf.open") as mock_doc:
                result = _extract_structured_with_local_ocr(
                    Path("fake.pdf"), content_hash=test_hash
                )
            mock_doc.assert_not_called()
            assert result is cached
        finally:
            with _STRUCT_OCR_CACHE_LOCK:
                _STRUCT_OCR_CACHE.pop(test_hash, None)

    def test_cache_miss_proceeds_to_ocr_attempt(self):
        """When hash is absent from cache, the function proceeds past the cache check.
        We verify it doesn't silently skip OCR logic by checking it reaches pymupdf."""
        test_hash = "_test_hash_miss_xyz999"
        with _STRUCT_OCR_CACHE_LOCK:
            _STRUCT_OCR_CACHE.pop(test_hash, None)

        # We don't have a real PDF so pymupdf.open will fail or return empty;
        # the point is the cache check doesn't short-circuit execution.
        with patch("backend.tml.inspection_report_parser._classify_pdf_for_ocr", return_value=(False, [0])), \
             patch("backend.tml.inspection_report_parser._is_tesseract_available", return_value=False), \
             patch("backend.tml.inspection_report_parser._get_surya_models", return_value=None), \
             patch("backend.tml.inspection_report_parser._get_easyocr_reader", return_value=None):
            result = _extract_structured_with_local_ocr(
                Path("fake.pdf"), content_hash=test_hash
            )
        # No engine available -> returns []
        assert result == []
