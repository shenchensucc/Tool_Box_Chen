"""
Dig Package Generator Page

Upload MDL, ILI data, and template files to generate dig packages.
"""

import io
import json
import sys
import time
import uuid
import zipfile
from pathlib import Path

import httpx
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    DIG_PACKAGE_ILI_FORMAT_OPTIONS,
    apply_custom_styling,
    check_backend_health,
    detect_dig_package_ili_format,
    display_header,
    display_sidebar_navigation,
    fu_key,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

set_page_config("Dig Package Generator", "📦")
apply_custom_styling()
display_sidebar_navigation()

main = get_layout_main()

with main:
    display_header(
        "📦 Dig Package Generator",
        "Generate dig package Excel and PDF files from MDL, ILI data, and template",
    )

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    if "dig_packages_generated" not in st.session_state:
        st.session_state.dig_packages_generated = False

    # -----------------------------------------------------------------------
    # Step 1 — MDL file + live preview
    # -----------------------------------------------------------------------
    st.markdown("### 📁 Step 1: Upload Source Files")
    st.info(
        """
        📋 **About This Tool**: Generate dig package files from MDL + ILI data, plus an **optional** template:
        - **MDL (Master Dig List)**: Contains dig IDs and target features
        - **ILI Data**: In-line inspection data with detailed feature information
        - **Template** (optional): If you omit it, the server uses the bundled **2026 Dig Package Template**.

        The tool will match features, populate templates, and generate Excel + PDF files for each dig ID.
        """
    )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**MDL File**")
        mdl_file = st.file_uploader(
            "Master Dig List (.xlsx)",
            type=["xlsx"],
            help="Excel file containing dig IDs and target features",
            key=fu_key("dp", "mdl"),
        )
        if mdl_file:
            st.success(f"✅ {mdl_file.name}")
            # Live preview — call preview endpoint to show found dig IDs.
            preview_key = f"mdl_preview_{mdl_file.name}_{mdl_file.size}"
            if st.session_state.get("_mdl_preview_key") != preview_key:
                with st.spinner("Reading MDL…"):
                    try:
                        with httpx.Client(timeout=30.0) as client:
                            resp = client.post(
                                f"{BACKEND_URL}/api/pipeline/dig-package/preview-mdl",
                                files={"mdl_file": (mdl_file.name, mdl_file.getvalue(), mdl_file.type)},
                            )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.session_state["_mdl_preview"] = data
                            st.session_state["_mdl_preview_key"] = preview_key
                        else:
                            st.session_state["_mdl_preview"] = None
                    except Exception:
                        st.session_state["_mdl_preview"] = None

            preview = st.session_state.get("_mdl_preview")
            if preview:
                ids = preview.get("dig_ids", [])
                if ids:
                    ids_display = ", ".join(str(i) for i in ids[:10])
                    if len(ids) > 10:
                        ids_display += f" … (+{len(ids) - 10} more)"
                    st.info(f"🔍 Found **{len(ids)} dig ID{'s' if len(ids) != 1 else ''}**: {ids_display}")
                else:
                    st.warning("⚠️ No valid dig IDs found in this MDL. Check that it contains a 'Dig ID' column with numeric IDs (e.g. 6000) or legacy IDs containing 'GW'.")
            elif st.session_state.get("_mdl_preview_key") == preview_key:
                st.warning("⚠️ Could not read MDL — check file format.")

    with col2:
        st.markdown("**Template File** (optional)")
        template_file = st.file_uploader(
            "Dig Package Template (.xlsx) — leave empty to use the default 2026 template on the server",
            type=["xlsx"],
            help="Excel template with named ranges. If omitted, the backend uses backend/static/templates/dig_package/2026 Dig Package Template.xlsx",
            key=fu_key("dp", "template"),
        )
        if template_file:
            st.success(f"✅ {template_file.name}")
        else:
            st.caption("📌 **Default template** will be used (2026 Dig Package Template bundled with the API).")

    # -----------------------------------------------------------------------
    # Step 2 — ILI files
    # -----------------------------------------------------------------------
    st.markdown("### 📊 Step 2: Upload ILI Data Files")
    st.info(
        "💡 Upload multiple ILI spreadsheets — **the layout is auto-detected from each filename** "
        "(TDW, Rosen MFL-A / MFL-C / EMAT, BH EMAT/MFL). Open **Override ILI format** only when the guess is wrong."
    )

    if "ili_files_data" not in st.session_state:
        st.session_state.ili_files_data = []

    uploaded_ili_files = st.file_uploader(
        "Upload ILI Data Files (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Excel files containing in-line inspection data",
        key=fu_key("dp", "ili"),
    )

    if uploaded_ili_files:
        new_ili_data = []
        for i, file in enumerate(uploaded_ili_files):
            st.markdown(f"**File {i+1}:** `{file.name}`")
            detected, detect_note = detect_dig_package_ili_format(file.name)
            st.caption(f"Suggested: **{detected}** — _{detect_note}_")
            with st.expander("Override ILI format (optional)", expanded=False):
                format_choice = st.selectbox(
                    "ILI layout",
                    options=list(DIG_PACKAGE_ILI_FORMAT_OPTIONS),
                    index=list(DIG_PACKAGE_ILI_FORMAT_OPTIONS).index(detected),
                    key=fu_key("dp", f"ili_fmt_{i}_{file.name}_{file.size}"),
                    help="Usually leave as suggested. Change only if the spreadsheet uses a different vendor layout.",
                )
            new_ili_data.append({"file": file, "format": format_choice})
        st.session_state.ili_files_data = new_ili_data

    # -----------------------------------------------------------------------
    # Step 3 — Configuration
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### ⚙️ Step 3: Configuration")

    col1, col2 = st.columns([1, 3])
    with col1:
        revision = st.text_input(
            "Revision Number",
            value="0",
            help="Revision identifier to append to output filenames (e.g., '1', '2', 'draft', etc.)",
        )
    with col2:
        st.markdown("**Naming Convention:**")
        st.caption(
            f"Output files: `{{Dig Name or Dig ID}}_DP_R{revision}.xlsx` / `.pdf` "
            "(matches PNG Integrity naming when **Dig Name** is present in the MDL)."
        )

    # -----------------------------------------------------------------------
    # Step 4 — Generate
    # -----------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 🚀 Step 4: Generate Dig Packages")

    st.markdown("#### Quick checks (no MDL / ILI required)")
    qc1, qc2 = st.columns([1, 2])
    with qc1:
        if st.button("⬇️ Fetch blank template ZIP", help="Downloads the bundled Excel template only — verifies API + browser download in seconds."):
            try:
                with httpx.Client(timeout=60.0) as _c:
                    br = _c.get(f"{BACKEND_URL}/api/pipeline/dig-package/blank-template-zip")
                if br.status_code == 200:
                    st.session_state["blank_template_zip"] = br.content
                    cd = br.headers.get("Content-Disposition") or ""
                    name = "Dig_Package_BLANK_TEMPLATE.zip"
                    if "filename=" in cd:
                        name = cd.split("filename=")[-1].strip().strip('"')
                    st.session_state["blank_template_filename"] = name
                else:
                    st.error(f"Blank template failed: HTTP {br.status_code}")
            except Exception as ex:
                st.error(f"Could not fetch blank template: {ex}")
    with qc2:
        if st.session_state.get("blank_template_zip") is not None:
            st.download_button(
                label="💾 Save blank template ZIP",
                data=st.session_state["blank_template_zip"],
                file_name=st.session_state.get("blank_template_filename", "blank.zip"),
                mime="application/zip",
                type="primary",
                key="download_blank_tpl_zip",
            )
            st.caption("Open the `.xlsx` inside: if it opens, the template path works. No MDL data were applied.")

    skip_pdf = st.checkbox(
        "Skip PDF (Excel only — recommended if generation times out)",
        value=True,
        key="dig_pkg_skip_pdf",
        help="PDF conversion uses Windows Excel COM automation and often causes multi‑minute hangs or HTTP timeouts. Uncheck only if you need PDF and Excel is responsive.",
    )
    skip_ili = st.checkbox(
        "Skip ILI parse (MDL-only — fast layout / template testing)",
        value=False,
        key="dig_pkg_skip_ili",
        help=(
            "Does not read ILI workbooks. Produces dig packages with MDL fields and empty feature tables. "
            "One HTTP POST still runs until the ZIP returns; there is no extra server cost beyond MDL + Excel writes. "
            "Turn on **Include debug JSON** to see mdl_col_map and per-dig values in the ZIP."
        ),
    )
    include_debug = st.checkbox(
        "Include debug JSON in ZIP (Dig_Package_Debug.json)",
        value=True,
        key="dig_pkg_include_debug",
        help="Adds column map and per-dig MDL values the backend resolved — useful while developing.",
    )

    with st.expander("📋 Development plan — smoke test & case study", expanded=False):
        st.markdown(
            """
**Why ILI parse can take many minutes**

The backend reads the **entire** vendor ILI Excel (sheet detection, header row, full DataFrame load). Large workbooks are inherently slow. That work happens **inside one** request — it is not “many API calls,” except your browser **polling** `GET /dig-package/progress/{job_id}` every few seconds for status text.

**Why “Skip ILI” exists**

For template/layout work you only need MDL → Excel anchors. **Skip ILI parse** skips reading ILI files entirely (still one POST until ZIP returns). Use **Include debug JSON** to inspect `mdl_col_map` and per-dig MDL values in `Dig_Package_Debug.json`.

**Why “first dig only” exists**

Full batches can take a long time or fail late if the template layout does not match
`dig_package_layout.json`. Generating **only the first dig ID** (MDL order) is the fastest
way to prove: MDL parse → ILI match → Excel population → ZIP download.

**Suggested workflow**

1. Use **Fetch blank template ZIP** (above) and save it — confirms download + API in seconds (no MDL/ILI).
2. For layout-only iteration: upload **MDL only**, enable **Skip ILI parse** + **Include debug JSON**, **Skip PDF**, then **Generate first dig only**.
3. For full pipeline: upload MDL + ILI, keep **Skip PDF** unless you need PDF (Excel COM often hangs or exceeds timeouts).
4. Open the summary JSON, `Dig_Package_Debug.json` (if included), and `.xlsx` in the ZIP.
5. If this works, run **Generate all dig packages** for the full program.

**What still needs human confirmation**

- Template **label text** must match anchors (run `python tools/dig_package_kpi/agent_loop.py --template path\\to\\template.xlsx` locally).
- **Joint Summary** sheet is not populated by this generator yet (tracked as KPI C-*).
- **Pytest** for automation: install dev deps, e.g. `pip install -e ".[dev]"` or `uv sync --extra dev`, then `pytest tests/test_dig_package_kpi.py`.
            """
        )

    all_files_uploaded = mdl_file is not None and (
        skip_ili or len(st.session_state.ili_files_data) > 0
    )

    if mdl_file is None:
        st.warning("⚠️ Upload a Master Dig List (MDL) Excel file.")
    elif not skip_ili and len(st.session_state.ili_files_data) == 0:
        st.warning("⚠️ Upload at least one ILI file, or enable **Skip ILI parse** for MDL-only packages. Template is optional.")

    def run_dig_package_generation(max_digs_value: str) -> None:
        job_id = str(uuid.uuid4())
        progress_bar = st.progress(0, text="Starting…")
        status_text = st.empty()
        # Long read timeout: Excel→PDF can block; prefer Skip PDF + 30 min read cap.
        long_timeout = httpx.Timeout(connect=60.0, read=3600.0, write=60.0, pool=60.0)

        try:
            files = [
                ("mdl_file", (mdl_file.name, mdl_file.getvalue(), mdl_file.type)),
            ]
            if template_file is not None:
                files.append(
                    ("template_file", (template_file.name, template_file.getvalue(), template_file.type))
                )
            ili_formats = []
            if not skip_ili:
                for item in st.session_state.ili_files_data:
                    files.append(("ili_files", (item["file"].name, item["file"].getvalue(), item["file"].type)))
                    ili_formats.append(item["format"])

            data = {"revision": revision, "job_id": job_id}
            if not skip_ili:
                data["ili_formats"] = ",".join(ili_formats)
            if max_digs_value.strip():
                data["max_digs"] = max_digs_value.strip()
            if skip_pdf:
                data["skip_pdf"] = "true"
            if skip_ili:
                data["skip_ili"] = "true"
            if include_debug:
                data["include_debug"] = "true"

            # Fire the generate request in a thread so we can poll progress alongside it.
            import threading

            response_holder: dict = {}
            error_holder: dict = {}

            def _run_generate():
                try:
                    with httpx.Client(timeout=long_timeout) as client:
                        resp = client.post(
                            f"{BACKEND_URL}/api/pipeline/dig-package/generate",
                            files=files,
                            data=data,
                        )
                    response_holder["response"] = resp
                except Exception as exc:
                    error_holder["error"] = exc

            gen_thread = threading.Thread(target=_run_generate, daemon=True)
            gen_thread.start()

            t0 = time.monotonic()
            poll_interval_sec = 5.0
            poll_client = httpx.Client(timeout=10.0)
            first_poll = True
            try:
                while gen_thread.is_alive():
                    time.sleep(1.0 if first_poll else poll_interval_sec)
                    first_poll = False
                    elapsed = int(time.monotonic() - t0)
                    try:
                        prog = poll_client.get(
                            f"{BACKEND_URL}/api/pipeline/dig-package/progress/{job_id}"
                        ).json()
                        current = prog.get("current", 0)
                        total = prog.get("total", 0)
                        stt = prog.get("status", "")
                        phase = (prog.get("phase") or "").strip()
                        msg = (prog.get("message") or "").strip()
                        long_parse = elapsed >= 120 and phase in (
                            "receiving_upload",
                            "parse_mdl",
                            "mdl_template",
                            "parse_ili",
                            "merge_ili",
                        )
                        warn = ""
                        if long_parse:
                            warn = (
                                "\n\n⚠️ **Still in parse/upload phase after 2+ minutes** — the backend "
                                "stops each ILI parse after a time limit (default **5 minutes**, env "
                                "`DIG_PACKAGE_ILI_PARSE_TIMEOUT_SEC`; use **0** for no limit). "
                                "Very large workbooks may need to be split or the limit raised on the server."
                            )
                        if total > 0:
                            pct = min(prog.get("pct", 0) / 100.0, 0.99)
                            label = f"{phase or 'running'} · {current}/{total} · {elapsed}s"
                            progress_bar.progress(pct, text=label[:80])
                            body = (
                                f"**Running…** `{elapsed}s`\n\n"
                                f"- **phase:** `{phase or '—'}`\n"
                                f"- **progress:** `{current}/{total}` · status `{stt}`\n"
                            )
                            if msg:
                                body += f"- **detail:** {msg}\n"
                            body += "\nZIP downloads when the request completes (PDF off = faster)."
                            body += warn
                            status_text.markdown(body)
                        else:
                            progress_bar.progress(0, text=f"{phase or 'preparing'}… ({elapsed}s)")
                            body = (
                                f"**{phase or 'Starting'}…** `{elapsed}s`\n\n"
                                f"{msg or 'Reading uploads or parsing MDL (see phase when set).'}"
                            )
                            body += warn
                            status_text.markdown(body)
                    except Exception:
                        status_text.caption(
                            f"Progress not available yet (`{elapsed}s`). "
                            "If this persists, confirm the backend is running and the job_id is registered."
                        )
            finally:
                poll_client.close()

            gen_thread.join()

            if "error" in error_holder:
                progress_bar.progress(0, text="Failed")
                status_text.markdown(f"**Request failed:** `{error_holder['error']!s}`")
                raise error_holder["error"]

            response = response_holder.get("response")
            if response is None:
                progress_bar.progress(0, text="Failed")
                status_text.markdown("**No HTTP response** from generation thread.")
                raise RuntimeError("Generation thread produced no response.")

            if response.status_code == 200:
                progress_bar.progress(1.0, text="Complete")
                status_text.markdown("**ZIP received** — saving results below.")
                st.session_state.dig_packages_zip = response.content
                disp = response.headers.get("Content-Disposition", "")
                st.session_state.dig_packages_filename = (
                    disp.split("filename=")[-1].strip('"') if "filename=" in disp
                    else f"Dig_Packages_R{revision}.zip"
                )
                st.session_state.dig_packages_generated = True

                # Parse summary from ZIP for results table.
                try:
                    with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
                        summary_names = [n for n in zf.namelist() if n.startswith("Dig_Package_Generation_Summary")]
                        if summary_names:
                            summary = json.loads(zf.read(summary_names[0]))
                            st.session_state.dig_packages_summary = summary
                        else:
                            st.session_state.dig_packages_summary = None
                except Exception:
                    st.session_state.dig_packages_summary = None

                st.success("✅ Dig packages generated successfully!")
                st.rerun()
            else:
                progress_bar.progress(0, text="Error")
                status_text.markdown(f"**HTTP {response.status_code}** — see error below.")
                try:
                    error_detail = response.json().get("detail", "Unknown error")
                except Exception:
                    error_detail = f"Server error ({response.status_code})"
                st.error(f"❌ Error generating dig packages: {error_detail}")

        except httpx.TimeoutException:
            st.error(
                "❌ Request timed out after 30 minutes (read limit). "
                "Enable **Skip PDF** above — PDF uses Excel COM and often hangs. "
                "Try **Generate first dig only** with Skip PDF checked."
            )
        except httpx.ConnectError:
            st.error("❌ Could not connect to the backend server. Please make sure it's running.")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

    gen_cols = st.columns(2)
    with gen_cols[0]:
        if st.button("🚀 Generate all dig packages", type="primary", disabled=not all_files_uploaded):
            run_dig_package_generation("")
    with gen_cols[1]:
        if st.button(
            "🧪 Generate first dig only",
            type="secondary",
            disabled=not all_files_uploaded,
            help="Processes only the first Dig ID in MDL order — fastest path to a downloadable ZIP for debugging.",
        ):
            run_dig_package_generation("1")

    # -----------------------------------------------------------------------
    # Step 5 — Download + results table
    # -----------------------------------------------------------------------
    if st.session_state.dig_packages_generated:
        st.markdown("---")
        st.markdown("### 📥 Step 5: Download Results")

        # Results table from summary JSON.
        summary = st.session_state.get("dig_packages_summary")
        if summary:
            generated = summary.get("generated", [])
            skipped = summary.get("skipped", [])
            failed_ili = summary.get("ili_files_failed", [])

            if failed_ili:
                st.warning(f"⚠️ {len(failed_ili)} ILI file(s) could not be parsed and were excluded: `{', '.join(failed_ili)}`")

            md = summary.get("max_digs")
            if md:
                st.info(
                    f"**Limited run:** `max_digs={md}` — only the first dig(s) in MDL order were processed. "
                    f"All IDs found in MDL: `{summary.get('dig_ids_in_mdl', [])}`"
                )

            if generated:
                import pandas as pd

                rows = []
                for item in generated:
                    rows.append({
                        "Dig ID": item.get("dig_id", ""),
                        "Dig Name": item.get("dig_name", ""),
                        "Features Matched": item.get("features_matched", ""),
                        "PDF": "✅" if item.get("pdf_generated") else "❌ (requires Excel)",
                        "Status": "✅ OK",
                    })
                for item in skipped:
                    rows.append({
                        "Dig ID": item.get("dig_id", ""),
                        "Dig Name": "",
                        "Features Matched": 0,
                        "PDF": "—",
                        "Status": f"⚠️ Skipped: {item.get('reason', '')}",
                    })

                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("Generated", len(generated))
            col_stat2.metric("Skipped", len(skipped))
            col_stat3.metric("ILI Sources", len(summary.get("ili_files", [])))

        st.download_button(
            label="💾 Download Dig Packages (ZIP)",
            data=st.session_state.dig_packages_zip,
            file_name=st.session_state.dig_packages_filename,
            mime="application/zip",
            type="primary",
        )

        if st.button("🔄 Generate New Batch"):
            for key in ["dig_packages_generated", "dig_packages_zip", "dig_packages_filename",
                        "dig_packages_summary", "_mdl_preview", "_mdl_preview_key"]:
                st.session_state.pop(key, None)
            st.rerun()

    # -----------------------------------------------------------------------
    # Help section
    # -----------------------------------------------------------------------
    with st.expander("ℹ️ Help & Requirements"):
        st.markdown(
            """
            ### File Requirements

            **MDL (Master Dig List)** must contain:
            - Dig ID column — accepts numeric IDs (e.g. 6000) or legacy IDs containing "GW"
            - Feature information (ID, Length, Width)
            - Pipe properties (OD, NWT, Grade, Year, MOP, SEP, etc.)
            - Assessment/Exposure information
            - Location data (Latitude, Longitude, Milepost)

            **ILI Data** must contain:
            - Feature ID or dimensions for matching
            - Feature properties (Type, Description, Depth, Length, Width, Orientation)
            - ILI Chainage for positioning
            - Joint Number for range filtering

            **Template** (optional — default 2026 template on server if omitted) is filled using
            **visible labels** + `dig_package_layout.json` (not Excel Name Manager). If your labels differ
            from the bundled template, adjust the layout JSON or upload a matching template.

            ### ILI Range Filtering

            Features included in each dig package are filtered by **3 girth welds upstream
            and 3 downstream** of the Target Girth Weld. When fewer than 3 GWDs exist on
            one side (e.g. near the start of the run), all available GWDs are included.

            ### Feature Matching Logic

            1. **Feature ID Matching** (Primary): Direct match by Feature ID
            2. **Dimension Matching** (Fallback): Match by Length and Width (with mm/inch conversion)

            Target features will be highlighted in **bold, red text with grey background**.

            ### Output Structure

            For each dig ID in the MDL, two files will be generated:
            - `{Dig Name or Dig ID}_DP_R{revision}.xlsx` — Excel dig package
            - Same stem `.pdf` — PDF version (requires Microsoft Excel on Windows)

            **PDF Note:** PDF conversion uses Microsoft Excel COM automation. This requires
            Microsoft Excel to be installed and `pywin32` (`pip install pywin32`).
            If unavailable, only Excel files are generated.

            ### Troubleshooting

            - **No dig packages generated**: Check that MDL has a Dig ID column with numeric IDs
              (e.g. 6000, 6001) or legacy IDs containing "GW"
            - **Features not matching**: Verify Feature IDs or dimensions match between MDL and ILI
            - **Blank or wrong cells**: Compare template label text to `dig_package_layout.json` anchors
            - **Large files**: Processing may take several minutes; a progress bar shows per-dig status
            """
        )

    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #95a5a6;'>
            <p>Dig Package Generator | Powered by Python + openpyxl</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_floating_chat_shell()
