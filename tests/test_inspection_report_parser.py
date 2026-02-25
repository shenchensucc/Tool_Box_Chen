"""
Tests for inspection report PDF parser.

Uses fixture: tests/fixtures/inspection_report_52-021K.pdf (Acuren UT report)
"""

import pytest
from pathlib import Path

from backend.tml.inspection_report_parser import parse_inspection_report_pdf
from backend.tml.inspection_dataloader import generate_measurements_dataloader, PLACEHOLDER_EQUIPMENT_ID


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "inspection_report_52-021K.pdf"

EXPECTED_52_021K = [
    ("52-021K", "1.01-1", 0.285),
    ("52-021K", "1.01-2", 0.299),
    ("52-021K", "1.05-1", 0.456),
    ("52-021K", "1.05-2", 0.450),
    ("52-021K", "1.05-3", 0.393),
    ("52-021K", "1.05-4", 0.405),
]


@pytest.mark.skipif(not FIXTURE_PATH.exists(), reason="Fixture PDF not found")
def test_parse_inspection_report_52_021k():
    """Parse Acuren fixture and verify expected Circuit, CML, Reading."""
    results = parse_inspection_report_pdf(FIXTURE_PATH, "inspection_report_52-021K.pdf")
    assert len(results) == len(EXPECTED_52_021K)
    for i, (circuit, cml, reading) in enumerate(EXPECTED_52_021K):
        assert results[i].circuit_id == circuit
        assert results[i].cml_id == cml
        assert abs(results[i].min_reading - reading) < 0.001
    assert results[0].measurement_date == "2026-02-23"


@pytest.mark.skipif(not FIXTURE_PATH.exists(), reason="Fixture PDF not found")
def test_generate_dataloader_from_parsed():
    """Verify dataloader generation from parsed readings."""
    readings = parse_inspection_report_pdf(FIXTURE_PATH, "inspection_report_52-021K.pdf")
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
