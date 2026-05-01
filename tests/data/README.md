# Test Fixtures — Metal Loss Mass Assessment

## TEST-R1R1-ML.xlsx

**Source:**
```
c:\Users\cshen\trisummit\PNG - Asset Integrity - Documents\General\003_TIMP\003_West_ML\000_Common\IDP\2026_Planning\01-EAs_including_2025_repair\R1-R2\TEST-R1R1-ML.xlsx
```

**What it is:** IDP planning spreadsheet for a West metal-loss pipeline segment.
Used as the ground-truth training set for the Mass Assessment tool.

**Sheet:** `MFL-A` — 137,249 rows × 37 columns

**Key input columns used by the tool:**
| Column | Role |
|--------|------|
| `As-Reported Anomaly Depth (%WT)` | Depth percentage (auto-detected) |
| `Length (mm)` | Defect axial length (auto-detected) |

**Expected output columns (ground truth):**
| Column | Description |
|--------|-------------|
| `Date to Become a Defect` | Calendar date depth hits 80 % WT |
| `Years to Become a Defect` | Years from ILI date to above date |
| `Failure Mode` | "Leak" for all metal-loss features |
| `Active/Inactive` | "Active" for all growing features |
| `2025` … `2035` | Pf (psi) for each year — 11 columns |

**Verified training rows (rows 2–3, used for formula validation):**
```
Row 2: depth=10.11 %WT, L=21.985 mm → Pf_2025=4010.44 psi, Years_to_defect=11.9251
Row 3: depth=21.89 %WT, L=152.615 mm → Pf_2025=3321.56 psi, Years_to_defect=9.5795
```

**How to install the fixture:**
Copy the source file to this folder and rename it:
```
tests/data/TEST-R1R1-ML.xlsx
```

The calibration script (`tests/test_mass_calibration.py`) will find it automatically.
If the file is missing it falls back to the original source path above.
