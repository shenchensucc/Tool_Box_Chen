"""Tests for inspection report PDF parser."""

import pytest
from pathlib import Path

from backend.tml.inspection_report_parser import parse_inspection_report_pdf
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
