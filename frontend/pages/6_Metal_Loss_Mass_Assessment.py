import sys
from pathlib import Path
from datetime import datetime, date
import httpx
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
            'mass_assess_result', 'mass_assess_filename',
            'mass_do', 'mass_tp', 'mass_YS', 'mass_TS',
            'mass_depth_tol', 'mass_length_tol', 'mass_depth_cr', 'mass_length_cr',
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

        @st.fragment
        def params_and_run():
            """Fragment: parameter changes only rerun this block, not the whole page."""
            with st.expander("Parameters", expanded=not uploaded_file):
                p1, p2 = st.columns(2)
                with p1:
                    do = st.number_input("Outside Diameter (mm)", min_value=0.0, value=273.1, step=0.1, key="mass_do")
                    tp = st.number_input("Wall Thickness (mm)", min_value=0.0, value=9.27, step=0.01, key="mass_tp")
                    YS = st.number_input("Yield Strength (MPa)", min_value=0.0, value=359.0, step=1.0, key="mass_YS")
                    TS = st.number_input("Tensile Strength (MPa)", min_value=0.0, value=455.0, step=1.0, key="mass_TS")
                with p2:
                    depth_tol = st.number_input("Depth Tolerance (%)", min_value=0.0, value=10.0, step=0.1, key="mass_depth_tol")
                    length_tol = st.number_input("Length Tolerance (mm)", min_value=0.0, value=0.0, step=1.0, key="mass_length_tol")
                    depth_cr = st.number_input("Depth CR (mm/yr)", min_value=0.0, value=0.47, step=0.01, key="mass_depth_cr",
                                               help="Depth corrosion rate in mm/year. Used for both Pf growth and Date to Become a Defect.")
                    length_cr = st.number_input("Length CR (mm/yr)", min_value=0.0, value=0.0, step=0.1, key="mass_length_cr")
                    ili_date_val = st.date_input(
                        "ILI Run Date",
                        value=date(datetime.now().year, 1, 1),
                        key="mass_ili_date",
                        help="Date of the ILI run. Sets the base year for Pf columns and the reference for 'Date to Become a Defect'.",
                    )
                st.caption("⚠️ Verify all parameters above, then check the box and click the button to run.")
                verified = st.checkbox("I have verified the parameters and am ready to run", value=False, key="mass_verified")
                run_clicked = st.button("🚀 Run Mass Assessment", type="primary", width="stretch", key="mass_run_btn")
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
                                "depth_cr": depth_cr, "length_cr": length_cr,
                                "start_year": ili_date_val.year,
                                "ili_date": ili_date_str,
                            }
                            with httpx.Client(timeout=600.0) as client:
                                response = client.post(
                                    f"{BACKEND_URL}/api/pipeline/metal-loss/mass-assess",
                                    files=files, data=data,
                                )
                            if response.status_code == 200:
                                st.session_state['mass_assess_result'] = response.content
                                st.session_state['mass_assess_filename'] = (
                                    f"Mass_Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d')}.xlsx"
                                )
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
                width="stretch",
                key="download_mass_assess"
            )
        else:
            st.caption("Run assessment to download")

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
        dimp_t = dimp_0 + (i × depth_cr)    [mm]
        Limp_t = Limp_0 + (i × length_cr)   [mm]
        ```

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

        #### Step 7: Limits
        When **dimp/tp > 0.80**, that cell shows **">80% leak"** (beyond B31G applicability).
        `Failure Mode` = **Leak** | `Active/Inactive` = **Active** for all metal-loss features.

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
