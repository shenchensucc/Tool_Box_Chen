import base64
import sys
from pathlib import Path
from datetime import datetime, date
import httpx
import pandas as pd
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    fu_key,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

# Page configuration
set_page_config("Metal Loss Mass Assessment", "📉")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

main = get_layout_main()

with main:
    # Header
    display_header(
        "📉 Metal Loss Mass Assessment",
        "Bulk assess metal loss features from Excel — 11-year Pf decay, defect date, and failure mode",
    )

    # Check backend status
    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    st.info(
        "📋 **About This Tool**: Upload an Excel file containing metal loss features (depth %, length mm) "
        "to calculate 11-year failure pressure decay (Pf, psi), estimated date to become a defect (80 % WT), "
        "failure mode, and active/inactive status for every feature."
    )

    # --- Integrated Process Flow (real workflow) ---
    st.subheader("📊 Process Flow")

    # Reset button - compact
    if st.button("🔄 Reset Tool", help="Clear all inputs and results"):
        keys_to_clear = [
            'mass_assess_result', 'mass_assess_filename', 'mass_assess_summary',
            'mass_do', 'mass_tp', 'mass_YS', 'mass_TS',
            'mass_depth_tol', 'mass_length_tol', 'mass_depth_cr', 'mass_length_cr',
            'mass_cr_low', 'mass_cr_mid', 'mass_cr_high',
            'mass_maop', 'mass_sf', 'mass_preset', 'mass_preset_applied',
            'mass_ili_date', 'mass_verified'
        ]
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()

    flow_col1, arrow1, flow_col2, arrow2, flow_col3 = st.columns([2, 0.3, 2, 0.3, 2])

    with flow_col1:
        st.markdown("""
        <div style="text-align: center; padding: 0.6rem; background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); 
                    border-radius: 12px; border: 2px solid #1976d2; margin-bottom: 0.5rem;">
            <div style="font-size: 1.5rem;">📁 <strong>1. UPLOAD</strong></div>
        </div>
        """, unsafe_allow_html=True)
        uploaded_file = st.file_uploader(
            "Excel file",
            type=["xlsx", "xls"],
            key=fu_key("mass", "excel"),
            label_visibility="collapsed",
        )
        if uploaded_file:
            st.caption(f"✓ {uploaded_file.name}")

    with arrow1:
        st.markdown("<div style='text-align: center; padding-top: 2rem; font-size: 1.5rem;'>→</div>", unsafe_allow_html=True)

    with flow_col2:
        st.markdown("""
        <div style="text-align: center; padding: 0.6rem; background: linear-gradient(135deg, #fff3e0 0%, #ffe0b2 100%); 
                    border-radius: 12px; border: 2px solid #e65100; margin-bottom: 0.5rem;">
            <div style="font-size: 1.5rem;">⚙️ <strong>2. CALCULATE</strong></div>
        </div>
        """, unsafe_allow_html=True)

        # Pipe presets: (OD mm, TP mm, YS MPa, TS MPa)
        PIPE_PRESETS = {
            "Custom": None,
            "NPS 10 (273.1) x 6.35 — Grade B (241/413)": (273.1, 6.35, 241.0, 413.0),
            "NPS 10 (273.1) x 9.27 — X52 (359/455)": (273.1, 9.27, 359.0, 455.0),
            "NPS 8 (219.1) x 8.18 — X52 (359/455)": (219.1, 8.18, 359.0, 455.0),
            "NPS 12 (323.9) x 9.53 — X52 (359/455)": (323.9, 9.53, 359.0, 455.0),
        }

        @st.fragment
        def params_and_run():
            """Fragment: parameter changes only rerun this block, not the whole page."""
            with st.expander("Parameters", expanded=not uploaded_file):
                # Seed pipe-spec defaults once; widgets below use session_state only
                # (no value=) so preset application never conflicts with defaults.
                for k, v in (("mass_do", 273.1), ("mass_tp", 9.27), ("mass_YS", 359.0), ("mass_TS", 455.0)):
                    st.session_state.setdefault(k, v)

                preset = st.selectbox("Pipe preset", list(PIPE_PRESETS.keys()), key="mass_preset",
                                      help="Pick a preset to pre-fill pipe spec, or Custom to enter manually.")
                pv = PIPE_PRESETS[preset]
                if pv and st.session_state.get("mass_preset_applied") != preset:
                    st.session_state["mass_do"], st.session_state["mass_tp"] = pv[0], pv[1]
                    st.session_state["mass_YS"], st.session_state["mass_TS"] = pv[2], pv[3]
                    st.session_state["mass_preset_applied"] = preset

                p1, p2 = st.columns(2)
                with p1:
                    do = st.number_input("Outside Diameter (mm)", min_value=0.0, step=0.1, key="mass_do")
                    tp = st.number_input("Wall Thickness (mm)", min_value=0.0, step=0.01, key="mass_tp",
                                         help="Global wall thickness. If the Excel has a wall-thickness column, per-row values are used where present.")
                    YS = st.number_input("Yield Strength (MPa)", min_value=0.0, step=1.0, key="mass_YS")
                    TS = st.number_input("Tensile Strength (MPa)", min_value=0.0, step=1.0, key="mass_TS")
                    maop = st.number_input("MAOP (psi) — 0 = not set", min_value=0.0, value=0.0, step=10.0, key="mass_maop",
                                           help="Maximum Allowable Operating Pressure. When set, features are classified Leak/Rupture and a Repair-By Year is computed. Leave 0 to skip (all features report Leak).")
                    sf = st.number_input("Safety Factor on MAOP", min_value=0.0, value=1.25, step=0.05, key="mass_sf",
                                         help="Repair criterion: Pf < MAOP x SF. Only used when MAOP is set.")
                with p2:
                    depth_tol = st.number_input("Depth Tolerance (%)", min_value=0.0, value=10.0, step=0.1, key="mass_depth_tol")
                    length_tol = st.number_input("Length Tolerance (mm)", min_value=0.0, value=0.0, step=1.0, key="mass_length_tol")
                    st.caption("Depth CR (mm/yr) by reported depth band:")
                    cr_low = st.number_input("CR: depth < 20% WT", min_value=0.0, value=0.47, step=0.01, key="mass_cr_low")
                    cr_mid = st.number_input("CR: depth 20–40% WT", min_value=0.0, value=0.47, step=0.01, key="mass_cr_mid")
                    cr_high = st.number_input("CR: depth > 40% WT", min_value=0.0, value=0.47, step=0.01, key="mass_cr_high")
                    length_cr = st.number_input("Length CR (mm/yr)", min_value=0.0, value=0.0, step=0.1, key="mass_length_cr")
                    ili_date_val = st.date_input(
                        "ILI Run Date",
                        value=date(datetime.now().year, 1, 1),
                        key="mass_ili_date",
                        help="Date of the ILI run. Sets the base year for Pf columns and the reference for 'Date to Become a Defect'.",
                    )
                st.caption("⚠️ Verify all parameters above, then check the box and click the button to run.")
                verified = st.checkbox("I have verified the parameters and am ready to run", value=False, key="mass_verified")
                run_clicked = st.button("🚀 Run Mass Assessment", type="primary", use_container_width=True, key="mass_run_btn")
            if run_clicked:
                if not uploaded_file:
                    st.warning("⚠️ Please upload an Excel file first.")
                elif not verified:
                    st.warning("⚠️ Please check the box to confirm you have verified the parameters before running.")
                elif verified:
                    with st.spinner("⏳ Processing..."):
                        try:
                            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                            ili_date_str = ili_date_val.strftime("%Y-%m-%d")
                            data = {
                                "do": do, "tp": tp, "YS": YS, "TS": TS,
                                "depth_tolerance": depth_tol, "length_tolerance": length_tol,
                                "depth_cr": cr_low,  # fallback rate; bands below take precedence
                                "length_cr": length_cr,
                                "depth_cr_low": cr_low, "depth_cr_mid": cr_mid, "depth_cr_high": cr_high,
                                "start_year": ili_date_val.year,
                                "ili_date": ili_date_str,
                                "safety_factor": sf,
                            }
                            if maop > 0:
                                data["maop_psi"] = maop
                            with httpx.Client(timeout=600.0) as client:
                                response = client.post(
                                    f"{BACKEND_URL}/api/pipeline/metal-loss/mass-assess",
                                    files=files, data=data,
                                )
                            if response.status_code == 200:
                                payload = response.json()
                                st.session_state['mass_assess_result'] = base64.b64decode(payload["file_b64"])
                                st.session_state['mass_assess_filename'] = payload["filename"]
                                st.session_state['mass_assess_summary'] = payload["summary"]
                                st.success("✅ Done!")
                                st.rerun()
                            else:
                                try:
                                    err = response.json().get("detail", response.text)
                                except Exception:
                                    err = response.text
                                st.error(f"❌ {err}")
                        except Exception as e:
                            st.error(str(e))

        params_and_run()

    with arrow2:
        st.markdown("<div style='text-align: center; padding-top: 2rem; font-size: 1.5rem;'>→</div>", unsafe_allow_html=True)

    with flow_col3:
        st.markdown("""
        <div style="text-align: center; padding: 0.6rem; background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); 
                    border-radius: 12px; border: 2px solid #2e7d32; margin-bottom: 0.5rem;">
            <div style="font-size: 1.5rem;">📥 <strong>3. DOWNLOAD</strong></div>
        </div>
        """, unsafe_allow_html=True)
        if 'mass_assess_result' in st.session_state:
            st.download_button(
                label="💾 Download Results (.xlsx)",
                data=st.session_state['mass_assess_result'],
                file_name=st.session_state['mass_assess_filename'],
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="download_mass_assess"
            )
        else:
            st.caption("Run assessment to download")

    # --- Results Summary ---
    if 'mass_assess_summary' in st.session_state:
        s = st.session_state['mass_assess_summary']
        st.subheader("📋 Results Summary")

        for w in s.get("warnings", []):
            st.warning(f"⚠️ {w}")

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total rows", s.get("total_rows", "—"))
        m2.metric("Assessed", s.get("valid_rows", "—"))
        m3.metric("Skipped", s.get("skipped_rows", "—"))
        if s.get("maop_psi"):
            m4.metric("Rupture / Leak", f"{s.get('rupture_count', 0)} / {s.get('leak_count', 0)}")
        else:
            m4.metric("Rupture / Leak", "MAOP not set")

        d1, d2 = st.columns(2)
        with d1:
            st.caption(
                f"**Detected columns** — depth: `{s.get('depth_column')}` · "
                f"length: `{s.get('length_column')}` · "
                f"feature ID: `{s.get('feature_id_column') or 'not found'}` · "
                f"wall thickness: `{s.get('wall_thickness_column') or 'not found (global TP used)'}`"
            )
            crs = s.get("corrosion_rates", {})
            if crs:
                st.caption(
                    f"**CR bands (mm/yr)** — <20%: {crs.get('band_lt20')} ({crs.get('rows_lt20')} rows) · "
                    f"20–40%: {crs.get('band_20_40')} ({crs.get('rows_20_40')} rows) · "
                    f">40%: {crs.get('band_gt40')} ({crs.get('rows_gt40')} rows)"
                )
        with d2:
            over80 = s.get("over_80_by_year", {})
            if over80:
                over80_df = pd.DataFrame(
                    {"Year": list(over80.keys()), "Features > 80% WT": list(over80.values())}
                )
                st.caption("**Features exceeding 80% WT by year**")
                st.dataframe(over80_df, hide_index=True, use_container_width=True, height=180)

        worst = s.get("worst_features", [])
        if worst:
            st.caption("**Top 20 worst features (lowest year-0 Pf)** — review these first")
            st.dataframe(pd.DataFrame(worst), hide_index=True, use_container_width=True, height=300)

        st.caption(
            "🔎 AI-assisted output — engineer review required before use in IDP planning "
            "or any regulatory submission."
        )

    # --- Equation & Calculation Logic ---
    with st.expander("📐 **Equation & Calculation Logic**", expanded=False):
        st.markdown("""
        ### Modified B31G Methodology

        The tool uses **Modified B31G** to compute failure pressure (Pf) for each defect at each year,
        and derives defect-scheduling outputs from the same growth model.

        #### Step 1: Apply Tolerances
        ```
        dimp_0 = (depth_pct + depth_tolerance) × 0.01 × tp   [mm]
        Limp_0 = length_mm  + length_tolerance                [mm]
        ```

        #### Step 2: Date to Become a Defect (80 % WT criterion)
        ```
        Years to Become a Defect = (tp × 0.80 − dimp_0) / depth_cr
        Date  to Become a Defect = ILI Date + Years × 365.25 days
        ```

        #### Step 3: Pf Growth (year i = 0 to 10, producing 11 columns)
        ```
        dimp_t = dimp_0 + (i × depth_cr_band)   [mm]
        Limp_t = Limp_0 + (i × length_cr)       [mm]
        ```
        The depth corrosion rate is banded by the reported depth:
        **< 20 % WT**, **20–40 % WT**, **> 40 % WT** — each band has its own rate input.
        Wall thickness is per-row when the Excel has a WT column, else the global TP.

        #### Step 4: Normalized Parameters
        ```
        z = Limp² / (do × tp)
        d/t = dimp / tp
        ```

        #### Step 5: Flow Stress & Folias Factor
        ```
        Sflow = YS + 69  [MPa]
        ```
        - **If z ≤ 50**: M = √(1 + 0.6275 z − 0.003375 z²)
        - **If z > 50**: M = 0.032 z + 3.3

        #### Step 6: Remaining Strength & Failure Pressure
        ```
        Rs     = (1 − 0.85 d/t) / (1 − 0.85 d/t / M)
        Po     = 2 × Sflow / (do/tp)
        Pf_psi = Po × Rs × 1000 × 0.14503774
        ```

        #### Step 7: Limits & Failure Mode
        When **dimp/tp > 0.80**, that cell shows **">80% leak"** (beyond B31G applicability).

        **With MAOP set:** a feature is **Rupture** if Pf drops below **MAOP × SF** while still
        under 80 % WT, otherwise **Leak**. A `Repair-By Year` column gives the first year either
        criterion is hit ("Beyond horizon" if neither occurs within the 11-year window).

        **Without MAOP:** all features report **Leak** and no Repair-By Year is computed.

        ---
        *Full documentation: `docs/functions/METAL_LOSS_MASS_ASSESSMENT.md`*
        """)

    # Help section
    with st.expander("ℹ️ Help & Instructions"):
        st.markdown("""
        **Step 1 – Upload:** Excel file with depth (% WT) and length (mm) columns.
        Column names are auto-detected (e.g. `As-Reported Anomaly Depth (%WT)`, `depth`, `Depth (%)`,
        `Length (mm)`, `length`).

        **Step 2 – Calculate:** Open Parameters to set pipe specs, tolerances, corrosion rates,
        and the ILI Run Date, then click Run.

        **Step 3 – Download:** Results Excel adds the following columns to your input data:
        | Column | Description |
        |--------|-------------|
        | `Date to Become a Defect` | Calendar date depth (with tolerance) reaches 80 % WT |
        | `Years to Become a Defect` | Years from ILI date to that threshold |
        | `Failure Mode` | Leak (metal loss default) |
        | `Active/Inactive` | Active (all growing features) |
        | `{year}` × 11 | Pf (psi) for each year from ILI year to ILI year + 10 |

        **Note:** Cells where depth exceeds 80 % WT in a given year show `>80% leak`.
        """)

    # Footer
    st.divider()
    st.caption("Metal Loss Mass Assessment Tool v2.0 | Chen's Engineer Toolbox")

render_floating_chat_shell()
