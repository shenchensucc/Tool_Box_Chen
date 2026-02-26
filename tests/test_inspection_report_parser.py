"""
Tests for inspection report PDF parser.

Fixtures:
- inspection_report_52-021K.pdf: Acuren 8"/6" format
- inspection_report_52-010B_1.29_1.37.pdf: CML 1.29, 1.37 (may need OCR if table is image)
- inspection_report_57-008U_1.52_1.29_4.09.pdf: Multi-section 16"/30"/8"/6" format
"""

import pytest
from pathlib import Path

from backend.tml.inspection_report_parser import parse_inspection_report_pdf
from backend.tml.inspection_dataloader import generate_measurements_dataloader, PLACEHOLDER_EQUIPMENT_ID


FIXTURE_52_021K = Path(__file__).parent / "fixtures" / "inspection_report_52-021K.pdf"
FIXTURE_52_010B = Path(__file__).parent / "fixtures" / "inspection_report_52-010B_1.29_1.37.pdf"
FIXTURE_57_008U = Path(__file__).parent / "fixtures" / "inspection_report_57-008U_1.52_1.29_4.09.pdf"

EXPECTED_52_021K = [
    ("52-021K", "1.01-1", 0.285),
    ("52-021K", "1.01-2", 0.299),
    ("52-021K", "1.05-1", 0.456),
    ("52-021K", "1.05-2", 0.450),
    ("52-021K", "1.05-3", 0.393),
    ("52-021K", "1.05-4", 0.405),
]


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


EXPECTED_57_008U = [
    ("57-008U", "1.52-1", 0.357),
    ("57-008U", "1.52-2", 0.358),
    ("57-008U", "1.29-1", 0.342),
    ("57-008U", "1.29-2", 0.287),
    ("57-008U", "1.29-3", 0.372),
    ("57-008U", "1.29-4", 0.382),
    ("57-008U", "4.09-1", 0.296),
    ("57-008U", "4.09-2", 0.326),
    ("57-008U", "4.09-3", 0.318),
]


@pytest.mark.skipif(not FIXTURE_57_008U.exists(), reason="Fixture PDF not found")
def test_parse_inspection_report_57_008u():
    """Parse multi-section fixture (CML 1.52, 1.29, 4.09) with 16\"/30\"/8\"/6\" zones."""
    results = parse_inspection_report_pdf(FIXTURE_57_008U, "inspection_report_57-008U.pdf")
    assert len(results) == len(EXPECTED_57_008U)
    for i, (circuit, cml, reading) in enumerate(EXPECTED_57_008U):
        assert results[i].circuit_id == circuit
        assert results[i].cml_id == cml
        assert abs(results[i].min_reading - reading) < 0.001
