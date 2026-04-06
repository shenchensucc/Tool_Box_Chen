"""Shared fixture expected values for inspection report parser tests and validation."""

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"

# (circuit_id, cml_id, min_reading) per fixture
FIXTURE_EXPECTED = {
    "inspection_report_52-021K.pdf": [
        ("52-021K", "1.01-1", 0.285),
        ("52-021K", "1.01-2", 0.299),
        ("52-021K", "1.05-1", 0.456),
        ("52-021K", "1.05-2", 0.450),
        ("52-021K", "1.05-3", 0.393),
        ("52-021K", "1.05-4", 0.405),
    ],
    "inspection_report_57-008U_1.52_1.29_4.09.pdf": [
        ("57-008U", "1.29-1", 0.342),
        ("57-008U", "1.29-2", 0.287),
        ("57-008U", "1.29-3", 0.372),
        ("57-008U", "1.29-4", 0.382),
        ("57-008U", "1.52-1", 0.357),
        ("57-008U", "1.52-2", 0.358),
        ("57-008U", "4.09-1", 0.296),
        ("57-008U", "4.09-2", 0.326),
        ("57-008U", "4.09-3", 0.318),
    ],
}
