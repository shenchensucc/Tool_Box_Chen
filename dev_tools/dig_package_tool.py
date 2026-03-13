"""
Dig Package Dev Tool

Local development tool for the dig package generator. Uses the same parser logic
as the app backend. Developers can:
- Run step-by-step parsing (MDL, ILI) with full feedback
- See column mappings, dig IDs, feature matching status
- Capture and display errors with full traceback
- Save training cases and validate against ground truth

Run: streamlit run dev_tools/dig_package_tool.py --server.runOnSave true
"""

import io
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

# Add project root for backend imports
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Ground truth directory for dig package cases
DIG_PACKAGE_GT_DIR = ROOT / "dev_tools" / "ground_truth_data" / "dig_package"
DIG_PACKAGE_GT_DIR.mkdir(parents=True, exist_ok=True)


def _load_training_summary() -> list[dict]:
    """Load summary of all dig package ground truth cases."""
    summary = []
    for p in sorted(DIG_PACKAGE_GT_DIR.glob("*_ground_truth.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            expected = data.get("expected", {})
            summary.append({
                "name": p.stem.replace("_ground_truth", ""),
                "dig_count": len(expected.get("dig_ids", [])),
                "mdl": data.get("source_files", {}).get("mdl", "?"),
            })
        except Exception:
            summary.append({"name": p.stem, "dig_count": 0, "mdl": "?"})
    return summary


def _run_with_error_capture(fn, *args, **kwargs):
    """Run function and return (result, error_msg, traceback_str)."""
    try:
        result = fn(*args, **kwargs)
        return result, None, None
    except Exception as e:
        tb_str = traceback.format_exc()
        return None, str(e), tb_str


def main():
    st.set_page_config("Dig Package Dev Tool", "📦", layout="wide")
    st.title("📦 Dig Package Dev Tool")
    st.caption(
        "Local tool for developers. Uses the same parser as the app. "
        "Step-by-step parsing with error capture. Save training cases for validation."
    )

    # --- Training Summary (sidebar) ---
    with st.sidebar:
        st.subheader("📋 Training Set Summary")
        summary = _load_training_summary()
        if summary:
            for s in summary:
                st.caption(f"📄 {s['name'][:40]}…" if len(s["name"]) > 40 else f"📄 {s['name']}")
                st.caption(f"   Expected {s['dig_count']} dig IDs")
            st.divider()
        else:
            st.info("No ground truth cases yet. Save one to get started.")

        st.subheader("⚙️ Options")
        run_full_generate = st.checkbox(
            "Run full generate (Excel+PDF)",
            value=False,
            help="If unchecked, only parse and show feedback (no ZIP output)",
        )

    # --- File input ---
    st.subheader("1. Load Files")
    col_upload, col_path = st.columns(2)

    with col_upload:
        st.markdown("**Upload files**")
        mdl_upload = st.file_uploader("MDL (.xlsx)", type=["xlsx"], key="dp_mdl")
        template_upload = st.file_uploader("Template (.xlsx)", type=["xlsx"], key="dp_tpl")
        ili_uploads = st.file_uploader(
            "ILI files (.xlsx)",
            type=["xlsx"],
            accept_multiple_files=True,
            key="dp_ili",
        )

    with col_path:
        st.markdown("**Or path to fixture (relative to project root)**")
        fixture_path = st.text_input(
            "Folder path containing MDL, ILI, template",
            placeholder="dev_tools/ground_truth_data/dig_package/case1/",
            key="dp_path",
        )

    # Resolve file contents
    mdl_content = None
    template_content = None
    ili_contents = []
    ili_formats = []
    source_names = {"mdl": "", "template": "", "ili": []}

    if mdl_upload and template_upload and ili_uploads:
        mdl_content = mdl_upload.read()
        template_content = template_upload.read()
        for f in ili_uploads:
            ili_contents.append(f.read())
            ili_formats.append("Rosen-MFLA")  # Default format
            source_names["ili"].append(f.name)
        source_names["mdl"] = mdl_upload.name
        source_names["template"] = template_upload.name
    elif fixture_path:
        folder = ROOT / fixture_path.strip()
        if folder.exists():
            xlsx_files = list(folder.glob("*.xlsx"))
            template_candidates = []
            for f in xlsx_files:
                fname_lower = f.name.lower()
                if "mdl" in fname_lower or ("dig" in fname_lower and "template" not in fname_lower) or "master" in fname_lower:
                    mdl_content = f.read_bytes()
                    source_names["mdl"] = f.name
                elif "template" in fname_lower:
                    template_content = f.read_bytes()
                    source_names["template"] = f.name
                elif "ili" in fname_lower or "tally" in fname_lower or "anomal" in fname_lower:
                    ili_contents.append(f.read_bytes())
                    ili_formats.append("Rosen-MFLA")
                    source_names["ili"].append(f.name)
                else:
                    template_candidates.append(f)
            if not template_content and template_candidates:
                template_content = template_candidates[0].read_bytes()
                source_names["template"] = template_candidates[0].name
        else:
            st.warning(f"Path not found: {folder}")

    if not mdl_content:
        st.info("Upload MDL, Template, and at least one ILI file, or enter a fixture path.")
        return

    if not template_content:
        st.warning("Template file not found. Using a placeholder - full generate may fail.")

    if not ili_contents:
        st.warning("No ILI files found. Add at least one ILI file.")

    # ILI format selector when multiple files
    if ili_contents:
        st.markdown("**ILI formats**")
        new_formats = []
        for i in range(len(ili_contents)):
            name = source_names["ili"][i] if i < len(source_names["ili"]) else f"ILI_{i+1}"
            sel = st.selectbox(
                name[:30] + ("…" if len(name) > 30 else ""),
                options=["Rosen-MFLA", "Rosen-MFLC", "Rosen-EMAT", "TDW"],
                key=f"dp_fmt_{i}",
            )
            new_formats.append(sel)
        ili_formats = new_formats

    revision = st.text_input("Revision", value="0", key="dp_rev")

    # --- Step 2: Parse MDL ---
    st.subheader("2. Parse MDL")
    from backend.pipeline.dig_package import (
        parse_mdl_file,
        extract_dig_ids,
        parse_ili_file,
        get_target_feature_indices,
        get_target_gw_chainage,
        filter_ili_data_by_range,
    )

    mdl_df = None
    mdl_col_map = {}
    dig_ids = []

    if mdl_content:
        result, err, tb = _run_with_error_capture(parse_mdl_file, mdl_content)
        if err:
            st.error(f"❌ MDL parse error: {err}")
            with st.expander("Full traceback"):
                st.code(tb, language="text")
        elif result:
            mdl_df, mdl_col_map = result
            st.success(f"✅ MDL parsed: {len(mdl_df)} rows, sheet columns mapped")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Column mapping**")
                mapping_df = pd.DataFrame(
                    [(k, v) for k, v in mdl_col_map.items()],
                    columns=["Standard", "Actual column"],
                )
                st.dataframe(mapping_df, use_container_width=True, hide_index=True)
            with col2:
                dig_ids = extract_dig_ids(mdl_df, mdl_col_map)
                st.markdown("**Dig IDs extracted**")
                if dig_ids:
                    st.success(f"Found {len(dig_ids)} dig IDs: {', '.join(dig_ids[:5])}{'…' if len(dig_ids) > 5 else ''}")
                    st.json(dig_ids)
                else:
                    st.warning("No valid Dig IDs (must contain 'GW')")
                    if mdl_col_map.get("dig_id"):
                        raw_ids = mdl_df[mdl_col_map["dig_id"]].dropna().unique().tolist()
                        st.caption(f"Raw values: {raw_ids[:10]}")

    # --- Step 3: Parse ILI ---
    st.subheader("3. Parse ILI")
    ili_parsed = []
    if ili_contents and mdl_df is not None:
        for i, (content, fmt) in enumerate(zip(ili_contents, ili_formats)):
            result, err, tb = _run_with_error_capture(parse_ili_file, content, fmt)
            if err:
                st.error(f"❌ ILI file {i + 1} ({fmt}): {err}")
                with st.expander(f"Traceback for {source_names['ili'][i] if i < len(source_names['ili']) else 'ILI'}"):
                    st.code(tb, language="text")
            elif result:
                df, col_map, sheet = result
                ili_parsed.append({"df": df, "col_map": col_map, "format": fmt})
                st.success(f"✅ ILI {i + 1} ({fmt}): {len(df)} rows, sheet '{sheet}'")
                with st.expander(f"ILI {i + 1} column mapping"):
                    st.dataframe(
                        pd.DataFrame([(k, v) for k, v in col_map.items()], columns=["Standard", "Actual"]),
                        hide_index=True,
                    )

    # --- Step 4: Feature matching preview ---
    if mdl_df is not None and mdl_col_map and ili_parsed and dig_ids:
        st.subheader("4. Feature Matching Preview")
        dig_id_col = mdl_col_map.get("dig_id")
        if dig_id_col:
            for dig_id in dig_ids[:5]:  # Show first 5
                mdl_features = mdl_df[mdl_df[dig_id_col] == dig_id]
                mdl_first = mdl_features.iloc[0]
                target_counts = []
                for ili_item in ili_parsed:
                    df = ili_item["df"]
                    col_map = ili_item["col_map"]
                    tgw = get_target_gw_chainage(mdl_first, df, mdl_col_map, col_map)
                    if tgw is not None:
                        df_f = filter_ili_data_by_range(df, tgw, mdl_first, mdl_col_map, col_map)
                    else:
                        df_f = df.copy()
                    targets = get_target_feature_indices(mdl_features, df_f, mdl_col_map, col_map)
                    target_counts.append(len(targets))
                st.caption(f"**{dig_id}**: {len(mdl_features)} MDL rows, targets matched: {target_counts}")
        if len(dig_ids) > 5:
            st.caption(f"… and {len(dig_ids) - 5} more dig IDs")

    # --- Step 5: Generate (optional) ---
    st.subheader("5. Generate" if run_full_generate else "5. Parse only (no generate)")
    if run_full_generate and mdl_content and template_content and ili_contents:
        if st.button("🚀 Generate Dig Packages", type="primary"):
            from backend.pipeline.dig_package import generate_dig_packages

            with st.spinner("Generating…"):
                result, err, tb = _run_with_error_capture(
                    generate_dig_packages,
                    mdl_content,
                    ili_contents,
                    template_content,
                    revision,
                    ili_formats,
                )
            if err:
                st.error(f"❌ Generate error: {err}")
                with st.expander("Full traceback"):
                    st.code(tb, language="text")
            elif result:
                zip_buffer = result
                st.success("✅ Dig packages generated!")
                st.download_button(
                    "📥 Download ZIP",
                    data=zip_buffer.getvalue(),
                    file_name=f"Dig_Packages_R{revision}.zip",
                    mime="application/zip",
                )
    else:
        st.caption("Check 'Run full generate' in sidebar to produce ZIP output.")

    # --- Save training case ---
    st.divider()
    st.subheader("6. Save Training Case")
    case_name = st.text_input("Case name", value="case1", key="dp_case")
    save_files = st.checkbox("Copy source files to ground truth folder", value=True, key="dp_save_files")
    if st.button("💾 Save ground truth"):
        case_folder = DIG_PACKAGE_GT_DIR / case_name
        if save_files and (mdl_content or ili_contents or template_content):
            case_folder.mkdir(parents=True, exist_ok=True)
            if mdl_content:
                (case_folder / source_names["mdl"]).write_bytes(mdl_content)
            if template_content:
                (case_folder / source_names["template"]).write_bytes(template_content)
            for i, (content, name) in enumerate(zip(ili_contents, source_names["ili"])):
                (case_folder / name).write_bytes(content)

        gt = {
            "case_name": case_name,
            "case_folder": case_name,
            "source_files": {
                "mdl": source_names["mdl"],
                "ili": source_names["ili"],
                "template": source_names["template"],
            },
            "ili_formats": ili_formats,
            "expected": {
                "dig_ids": dig_ids,
                "dig_count": len(dig_ids),
            },
            "extracted_at": datetime.now().isoformat(),
            "schema_version": "1.0",
        }
        out_path = DIG_PACKAGE_GT_DIR / f"{case_name}_ground_truth.json"
        out_path.write_text(json.dumps(gt, indent=2), encoding="utf-8")
        st.success(f"Saved {out_path.name}" + (f" + files to {case_name}/" if save_files else ""))

    st.caption("Dig Package Dev Tool | Not part of production app")


if __name__ == "__main__":
    main()
