# Dev Tools

Local development tools for Chen's Engineer Toolbox. **Not part of the production app.**

## Inspection Report Ground Truth

Tool for iterating on the facility report reading parser with developers and AI.

### Purpose

- Use the **exact same parser logic** as the app backend
- Review extracted readings in a table
- **Mark wrong readings** (checkbox) and enter corrected values
- **Add missing readings** the parser failed to extract
- Export to JSON for training/ground-truth datasets
- **Training set summary** in sidebar (all ground truth files, PDF status)
- **Include PDF text** in export for debugging (raw text from each page, per-reading context)

### Run

```bash
# From project root (auto-reloads when code changes)
streamlit run dev_tools/inspection_report_ground_truth.py --server.runOnSave true
```

Or with custom port:

```bash
streamlit run dev_tools/inspection_report_ground_truth.py --server.runOnSave true --server.port 8502
```

### Usage

1. **Load PDF**: Upload a file or enter path like `dev_tools/ground_truth_data/52-001G 1-1 2.32 UT-ROBJOS-26-063_02.28.2026.pdf`
2. **Review**: Table shows Circuit, CML, Min Reading, Date. Uncheck "✓ Correct" for wrong rows; fill "Corrected" with the right value
3. **Add rows**: Edit the additions table (add/remove rows in place). All edits are in-memory until Save
4. **Export**: Check "Include PDF text" for debugging context. Download JSON or click **Save** to write JSON + original PDF to `dev_tools/ground_truth_data/`

### Ground Truth Format

Exported JSON can be used for:

- Pytest fixtures (expected values)
- Parser validation
- Training data for future improvements

```json
{
  "source_file": "inspection_report_52-021K.pdf",
  "readings": [
    {"circuit_id": "52-021K", "cml_id": "1.01-1", "min_reading": 0.285, "is_correct": true},
    {"circuit_id": "52-021K", "cml_id": "1.01-2", "min_reading": 0.299, "is_correct": false, "expected_reading": 0.300}
  ],
  "additions": [{"circuit_id": "52-021K", "cml_id": "1.01-5", "min_reading": 0.410}]
}
```

### Validation Script

Validate the parser against ground truth and fixtures:

```bash
python dev_tools/validate_ground_truth.py
python dev_tools/validate_ground_truth.py --fixtures-only   # Skip ground truth when PDFs missing
```

- Runs fixture tests (52-021K, 57-008U)
- Validates ground truth JSON when the matching PDF exists (saved alongside JSON in `ground_truth_data/`, or in `tests/fixtures/`)

---

## Dig Package Dev Tool

Tool for iterating on the dig package generator with error capture and training cases.

### Purpose

- Use the **exact same parser logic** as the app backend
- **Step-by-step parsing** (MDL → ILI → feature matching) with full feedback
- **Capture errors** in frontend with full traceback
- **Column mapping** and dig ID extraction visibility
- Save training cases and validate against ground truth

### Run

```bash
streamlit run dev_tools/dig_package_tool.py --server.runOnSave true
```

### Usage

1. **Load files**: Upload MDL, ILI, and template, or enter fixture path like `dev_tools/ground_truth_data/dig_package/case1/`
2. **Parse MDL**: See column mapping and extracted dig IDs
3. **Parse ILI**: See column mapping per ILI file
4. **Feature matching**: Preview target feature counts per dig ID
5. **Generate** (optional): Check "Run full generate" in sidebar to produce ZIP
6. **Save training case**: Enter case name, optionally copy files, click Save

**Synergy with ILI Visual Tool**: Generated dig package Excel files can be visualized in the **ILI Visual Tool** (Dig Package input format). The same `dig_package_reader` module parses the Feature summary and Joint Summary sections for the pipeline visual.

---

## ILI Visual Dig Package Dev Tool

Tool for iterating only on the **ILI Visual Tool** dig package parser and blue-line logic.

### Purpose

- Use the **exact same parser logic** as the ILI Visual dig package flow
- Upload a single dig package and inspect what the visual path can actually read
- Show **section detection** for `Feature summary` and `Joint Summary`
- Show **column mapping**, parsed joint-summary rows, girth welds, seam spans, and target GWD longseam
- Export a compact JSON snapshot for debugging and logic revision

### Run

```bash
streamlit run dev_tools/ili_visual_dig_package_tool.py --server.runOnSave true
```

### Usage

1. Upload one dig package Excel file, or enter a path relative to project root
2. Review section metadata and the final column mapping used by the visual path
3. Compare raw `Feature summary` / `Joint Summary` tables against parsed outputs
4. Inspect the built `girth_welds` and `seam_welds` payloads to debug missing blue lines
5. Download the JSON snapshot when you want to share a reproducible parser case

### Ground Truth Format

Saved to `dev_tools/ground_truth_data/dig_package/`:

```json
{
  "case_name": "case1",
  "case_folder": "case1",
  "source_files": {"mdl": "mdl.xlsx", "ili": ["ili.xlsx"], "template": "template.xlsx"},
  "ili_formats": ["Rosen-MFLA"],
  "expected": {"dig_ids": ["GW1", "GW2"], "dig_count": 2},
  "schema_version": "1.0"
}
```

When "Copy source files" is checked, files are saved to `dig_package/case1/` for validation.

### Validation Script

```bash
python dev_tools/validate_dig_package.py
```

Compares parsed dig IDs against expected dig IDs in ground truth JSON. MDL file must exist in `case_folder/` or `ground_truth_data/dig_package/`.
