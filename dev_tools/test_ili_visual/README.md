# ILI Visual Tool — Test Harness

Tests the ILI Visual Tool backend against real Excel files.
Each test case uploads a file, calls `/api/ili/process-feature-map`, and checks
the response against declared expectations.

---

## Prerequisites

- Python environment with project dependencies installed (`httpx` is required)
- The FastAPI backend **running** locally

---

## Quick start (on a machine without AV restrictions)

```bash
# Terminal 1 — backend
uvicorn backend.main:app --reload

# Terminal 2 — tests
python dev_tools/test_ili_visual/run_tests.py
```

Save a report to file:
```bash
python dev_tools/test_ili_visual/run_tests.py --report dev_tools/test_ili_visual/last_report.md
```

Run only specific cases:
```bash
python dev_tools/test_ili_visual/run_tests.py pipe_tally_209_240_manual
```

Override backend URL (e.g. if running on a different port):
```bash
python dev_tools/test_ili_visual/run_tests.py --backend http://127.0.0.1:8001
```

---

## Iteration workflow

This is the recommended loop when adding support for a new file type:

```
1. Run tests
       ↓ see FAIL / column not detected
2. Read the "info" block in the output
   → "Actual columns in sheet: ['GWD No.', 'US Odo (m)', 'DS Odo (m)', ...]"
       ↓
3. Add the missing column names to COLUMN_KEYWORDS in
   backend/pipeline/ili_reader.py
   (or fix detect_data_format() if the wrong format was detected)
       ↓
4. Restart the backend (Ctrl-C → uvicorn backend.main:app --reload)
       ↓
5. Re-run tests  →  repeat until all green
```

---

## Adding a new test case

Open `test_cases.json` and add an object to the `"test_cases"` array:

```jsonc
{
  "id": "my_new_file",                       // unique, no spaces
  "description": "Short human description",
  "file_path": "C:\\path\\to\\file.xlsx",    // absolute path, double backslashes
  "mode": "manual_sheet",                    // "manual_sheet" | "vendor_auto"
  "sheet_name": "Sheet Name",               // for manual_sheet mode
  "vendor_format": "Rosen-MFLA",           // for vendor_auto mode
  "data_format_override": "auto",           // "auto" | "anomaly" | "pipe_tally"
  "skip": false,                            // set true to skip temporarily
  "expected": {
    "success": true,
    "data_format": "pipe_tally",           // omit to skip this check
    "min_rows": 10,                        // omit to skip row count check
    "column_keys_required": [             // FAIL if any of these are not detected
      "distance",
      "joint_number"
    ],
    "column_keys_preferred": [            // NOTE (not FAIL) if missing
      "ds_distance",
      "wall_thickness",
      "pipe_grade",
      "orientation"
    ],
    "has_girth_welds": true,              // true | false | "any" (just log)
    "has_seam_welds": "any"
  }
}
```

---

## Registered data formats

| Key          | Description                    | Builder function                        |
|--------------|--------------------------------|-----------------------------------------|
| `anomaly`    | ILI Anomaly / Feature Data     | `build_feature_map_from_df`             |
| `pipe_tally` | Pipe Tally (Joint Inventory)   | `build_feature_map_from_pipe_tally_df`  |

To add a new format: see `backend/pipeline/feature_map_builder.py` → `DATA_FORMAT_BUILDERS`.

---

## Test case inventory

| ID | File | Mode | Format expected |
|----|------|------|-----------------|
| `pipe_tally_209_240_manual` | Test 209-240.xlsx / Pipe Tally | manual_sheet | pipe_tally |
| `pipe_tally_209_240_forced` | Test 209-240.xlsx / Pipe Tally | manual_sheet (forced) | pipe_tally |
| `dig_correlation_sheet` | Test 209-240.xlsx / Dig Correlation | manual_sheet | auto |
| `rosen_mfla_vendor_auto` | *(template — skipped)* | vendor_auto | anomaly |
