# Dig package template — first principles (beyond Excel defined names)

## Why move away from “cell names only”

Excel **defined names** (`tmp_DigID_`, …) are a **hidden contract**: they are not obvious when someone opens the workbook, they are easy to typo, and if missing the generator **silently skips** the cell. That is the opposite of how people edit templates: they follow **visible labels**, **sections**, and **tables**.

You **can** stop depending on defined names as the *primary* addressing scheme. The replacement is an **explicit, reviewable mapping** from “what we mean” (logical fields) to “where it lives on this sheet,” using rules that match **human reading order**.

---

## How humans actually read or change a template

1. **Sheet** — “I’m on the cover / Dig Package sheet.”
2. **Section** — “This block is Description / Pipe / Location.”
3. **Label cell** — A cell that **shows** the text *Dig Name*, *Pipeline Name*, *Rev #*, etc. (often left column or merged header).
4. **Value cell** — Usually **to the right of the label**, **under a header**, or **inside a table row** — the blank where data goes.
5. **Version** — “This is the 2026 template” — layout and row positions may change between years.

**First principle:** A generator should resolve “where to write Dig Name” the same way a human would: **find the anchor (label or section title), then apply a fixed rule for where the value goes** — not require a parallel naming system only machines see in Name Manager.

---

## Recommended strategies (pick one per template family)

### A. **Anchor + offset (label-driven)** — closest to human editing

- **Anchor:** Exact string (or stable regex) on the sheet, e.g. cell containing `Dig Name` (or `Dig Name:`).
- **Rule:** Value is at **offset** `(dx, dy)` from the anchor (e.g. one column to the right), or **first empty cell in the same row to the right of the label**.
- **Pros:** Survives **column insertions** if the label moves with the block; reviewers see the same text they edit.
- **Cons:** Breaks if the **label text** changes (“Dig Name” → “Dig ID Name”); must update anchor rules in one place (manifest).

### B. **Section box + relative grid** — “Description table” as a region

- **Anchor:** Section title cell, e.g. `Description` (merged header).
- **Rule:** Within a bounded **row/column box** below that header, fill fields by **row index + column index** within the box (e.g. row 3 = Dig Name value column 2).
- **Pros:** Stable if the whole block moves as one.
- **Cons:** If someone inserts a row **inside** the box, indices shift — version the template or bump a **layout version** in the manifest.

### C. **Explicit coordinates in a manifest (sheet + A1)** — simplest for automation

- **Rule:** `dig_name` → `Cover!C5` (example). No Name Manager, no search.
- **Pros:** Trivial to implement; easy to diff in Git.
- **Cons:** Breaks on **any** row/column shift unless you **bump template version** and update the manifest together.

**Defined names** can remain as **optional shortcuts** (Excel users can still use Name Manager), but the **source of truth** for generation should be the **manifest + rules**, not the other way around.

---

## Rules to adopt (project policy)

1. **One template version → one mapping artifact**  
   Ship a file alongside the template (e.g. `2026_Dig_Package_Template.mapping.yaml`) that lists every logical field and how to find it (anchors, offsets, or `sheet!A1`). **No** silent reliance on undefined names.

2. **Fail loud on mismatch**  
   At generation time, if an anchor string is not found or a box is out of bounds, **raise a clear error** listing the field and what was searched for — not a silent blank cell.

3. **Human review**  
   The mapping file should be readable by non-developers (“Dig Name = cell to the right of label `Dig Name` on sheet Dig Package”). Prefer that over a table of opaque `tmp_*` names.

4. **Version coupling**  
   Template filename or internal `TemplateVersion` cell should match the manifest. If someone changes the Excel layout, they **must** update the manifest (or CI fails).

5. **Migration path**  
   - **Phase 1:** Implement resolver: `logical_field → cell` using manifest; keep existing `get_cell_from_named_range` as **fallback** if manifest says `use_defined_name: tmp_DigID_`.  
   - **Phase 2:** New templates use only manifest/anchors; **deprecate** `tmp_*` in docs and KPIs.  
   - **Phase 3:** Remove name-based path when no longer needed.

6. **KPI / tests**  
   Replace “named range exists” checks with “mapping resolves for template version X” and optional golden-file output for one dig.

---

## Relation to current code (implemented)

`backend/pipeline/dig_package_layout.py` loads **`backend/static/templates/dig_package/dig_package_layout.json`** and resolves each logical field by **anchor text + offset**. `populate_single_value_fields`, `populate_excavation_summary`, and `populate_feature_table` use this manifest (Excel **defined names are no longer required** for population, though `get_cell_from_named_range` remains in the file for legacy reference).

**How to verify one-by-one (dev):**

1. **CLI:** `python tools/verify_dig_package_layout.py path\to\template.xlsx` — prints `OK` / `FAIL` per field and block (`[excavation_summary]`, `[feature_table]`, …). Exit code `1` if any anchor is missing.
2. **Unit tests:** `pytest tests/test_dig_package_layout.py tests/test_dig_package.py` — anchor resolution and a minimal label-based workbook.
3. **Override manifest:** set env `DIG_PACKAGE_LAYOUT_JSON` to a custom JSON path when testing alternate templates.

---

## Summary

| Approach              | Human-visible | Robust to small edits | Easy to validate |
|---------------------|---------------|------------------------|------------------|
| Defined names only  | No            | No (silent miss)       | Weak             |
| Anchor + offset     | Yes           | Medium                 | Strong if labels stable |
| Section + grid      | Yes           | Medium                 | Strong with version pins |
| Manifest coordinates| Yes (in file) | Low unless versioned   | Very strong      |

**Recommendation:** Adopt a **versioned mapping manifest** plus **anchor+offset** for description fields (where labels exist), and **coordinates or table anchors** for feature tables — and **require** resolution errors to surface to the user when the template layout and mapping diverge.
