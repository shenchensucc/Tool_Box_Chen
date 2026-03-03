# Inspection Report Training Set Summary

## All Training Sets (unified)

| Source | PDF Location | Ground Truth |
|-------|--------------|--------------|
| **Pre-dev_tools fixtures** | tests/fixtures/ | dev_tools/ground_truth_data/ |
| inspection_report_52-021K | tests/fixtures/ | inspection_report_52-021K_ground_truth.json |
| inspection_report_57-008U (1.52, 1.29, 4.09) | tests/fixtures/ | inspection_report_57-008U_1.52_1.29_4.09_ground_truth.json |
| **Dev tools ground truth** | dev_tools/ground_truth_data/ | dev_tools/ground_truth_data/ |
| 52-001A 1-1 11.05 UT-ROBJOS-26-065 | ✅ dev_tools/ground_truth_data/ | 52-001A 1-1 11.05 UT-ROBJOS-26-065_02.28.2026_ground_truth.json |
| 52-001C 1-2 CML 1.33 UT-BALJIN-2026-18 | ✅ dev_tools/ground_truth_data/ | 52-001C 1-2 CML 1.33 UT-BALJIN-2026-18-02.28.2026_ground_truth.json |
| 52-001G 1-1 2.32 UT-ROBJOS-26-063 | ✅ | 52-001G 1-1 2.32 UT-ROBJOS-26-063_02.28.2026_ground_truth.json |
| 57-034B 4-4 CML 2.30 UT-BALJIN-2026-15 | ✅ | 57-034B 4-4 CML 2.30 UT-BALJIN-2026-15-02.27.2026_ground_truth.json |
| 57-034C 4-7 2.37UT-ROBJOS-26-061 | ✅ | 57-034C 4-7 2.37UT-ROBJOS-26-061_02.27.2026_ground_truth.json |

| inspection_report_52-010B (1.29, 1.37) | tests/fixtures/ | inspection_report_52-010B_1.29_1.37_ground_truth.json |

**Note:** 52-010B ground truth has 6 expected rows (1.29-1..3, 1.37-1..3) with placeholder values. Parser currently returns 2 rows; validation will fail until parser/OCR extracts the image-based results table. Fill correct values via dev_tools UI.
