# Metal Loss Mass Assessment

## Overview

The Metal Loss Mass Assessment tool performs bulk failure pressure (Pf) calculations for pipeline metal loss features from an Excel file. It projects each feature over 10 years using user-defined corrosion rates and outputs the failure pressure decay for each year.

## Purpose

- **Bulk Processing**: Assess hundreds or thousands of metal loss features in a single operation
- **10-Year Projection**: Calculate Pf for each feature at years 0 through 9 from the ILI run date
- **Modified B31G Methodology**: Industry-standard pipeline defect assessment
- **Excel In/Out**: Upload ILI data, download results with new columns appended

## Process Flow

```
┌─────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  1. UPLOAD      │     │  2. CALCULATE       │     │  3. DOWNLOAD        │
│  Excel file     │ ──► │  Backend applies    │ ──► │  Results Excel      │
│  (depth, length)│     │  Modified B31G      │     │  with Year X Pf      │
│                 │     │  for 10 years       │     │  columns             │
└─────────────────┘     └─────────────────────┘     └─────────────────────┘
```

## API Endpoint

- **POST** `/api/pipeline/metal-loss/mass-assess`
- **Location**: `backend/main.py`
- **Logic**: `backend/pipeline/metal_loss.py` → `mass_assess_metal_loss()`

### Form Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `file` | UploadFile | Excel file (.xlsx, .xls) |
| `do` | float | Outside diameter (mm) |
| `tp` | float | Wall thickness (mm) |
| `YS` | float | Yield strength (MPa) |
| `TS` | float | Tensile strength (MPa) |
| `depth_tolerance` | float | ILI depth tolerance (%) |
| `length_tolerance` | float | ILI length tolerance (mm) |
| `depth_cr` | float | Depth corrosion rate (mm/yr), default 4.0 |
| `length_cr` | float | Length corrosion rate (mm/yr), default 25.0 |
| `start_year` | int | Year of ILI run |

### Output

- Excel file with original columns plus:
  - `Year {start_year} Pf (psi)` ... `Year {start_year+9} Pf (psi)`
  - `Debug_Feature_ID`, `Debug_Initial_Depth_mm`, `Debug_Initial_Length_mm`

## Input File Requirements

### Required Columns

The tool uses `identify_ili_columns()` to auto-detect columns by keyword. At minimum:

- **Depth**: Column containing defect depth (e.g., `depth`, `Depth (%)`, `Max. Depth`, `Peak Depth (% WT)`)
- **Length**: Column containing defect length (e.g., `length`, `Length`, `defect length`, `Length (mm)`)

See `backend/pipeline/ili_reader.py` → `COLUMN_KEYWORDS` for full list.

### Data Requirements

- Depth: numeric, typically % of wall thickness (e.g., 50 for 50%)
- Length: numeric, in mm
- Rows with depth ≤ 0 or length ≤ 0 are skipped (result = blank)

## Calculation Logic

### Step 1: Apply Tolerances

```
dimp_0 = (depth_percent + depth_tolerance) × 0.01 × tp    [mm]
Limp_0 = length_raw + length_tolerance                     [mm]
```

- `depth_percent`: ILI-reported depth as % of wall thickness
- `tp`: nominal wall thickness (mm)

### Step 2: 10-Year Defect Growth

For each year `i` = 0, 1, ..., 9:

```
dimp_t = dimp_0 + (i × depth_cr)    [mm]
Limp_t = Limp_0 + (i × length_cr)    [mm]
```

### Step 3: Failure Pressure (Modified B31G)

The failure pressure Pf is calculated using the Modified B31G method:

#### 3.1 Normalized Parameters

```
z = L² / (do × tp)
d/t = dimp / tp
```

- `L`: defect length (mm)
- `do`: outside diameter (mm)
- `tp`: wall thickness (mm)

#### 3.2 Flow Stress

```
Sflow = YS + 69    [MPa]
```

#### 3.3 Folias Factor (M)

- **If z ≤ 50** (shorter defects):
  ```
  M = √(1 + 0.6275z - 0.003375z²)
  ```

- **If z > 50** (longer defects):
  ```
  M = 0.032z + 3.3
  ```

#### 3.4 Remaining Strength Factor (Rs)

```
Rs = (1 - 0.85 × d/t) / (1 - 0.85 × d/t / M)
```

#### 3.5 Failure Pressure

```
Po = 2 × Sflow / (do / tp)    [defect-free pipe, MPa]
Pf = Po × Rs × 1000           [kPa]
Pf_psi = Pf × 0.14503774      [psi]
```

### Step 4: >80% Wall Thickness Handling

If `dimp_t / tp > 0.80` for any year, the result for that year is set to `">80% leak"` instead of a numeric Pf (beyond applicability range of B31G).

## Output Columns

| Column | Description |
|--------|-------------|
| All original columns | Preserved from input |
| `Year {Y} Pf (psi)` | Failure pressure in psi for year Y |
| `Debug_Feature_ID` | Feature identifier (if column found) |
| `Debug_Initial_Depth_mm` | dimp_0 used in calculation |
| `Debug_Initial_Length_mm` | Limp_0 used in calculation |

## Frontend

- **Page**: `frontend/pages/6_Metal_Loss_Mass_Assessment.py`
- **Route**: Pipeline → Metal Loss Mass Assessment

## Implementation References

- **Core logic**: `backend/pipeline/metal_loss.py`
  - `mass_assess_metal_loss()` - main bulk function
  - `calculate_failure_pressure()` - Pf calculation
  - `calculate_folias_factor()` - Folias factor M
- **Column mapping**: `backend/pipeline/ili_reader.py` → `identify_ili_columns()`

## Testing

- **Unit tests**: `tests/test_metal_loss.py`
- **Validation**: See `TESTING_GUIDE.md` for expected values (Test Cases 1 & 2 use same underlying formulas)

---

**Last Updated**: February 2025
