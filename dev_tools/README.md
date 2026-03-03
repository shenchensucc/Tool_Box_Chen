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
