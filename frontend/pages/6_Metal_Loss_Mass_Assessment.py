import sys
from pathlib import Path
from datetime import datetime
import httpx
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    get_layout_with_chat,
    set_page_config,
    show_backend_unavailable_and_retry,
    BACKEND_URL,
)
from chat_panel import render_chat_expander

# Page configuration
set_page_config("Metal Loss Mass Assessment", "📉")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

cols, chat_visible = get_layout_with_chat()
left_col, right_col = cols

with left_col:
    # Header
    display_header(
        "📉 Metal Loss Mass Assessment",
        "Bulk assess metal loss features from Excel for 10-year pressure decay",
    )

    # Check backend status
    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    st.info("📋 **About This Tool**: Upload an Excel file containing metal loss features (depth, length) to calculate the 10-year failure pressure decay for all features at once.")

    # --- Integrated Process Flow (real workflow) ---
    st.subheader("📊 Process Flow")

    # Reset button - compact
    if st.button("🔄 Reset Tool", help="Clear all inputs and results"):
        keys_to_clear = [
            'mass_assess_result', 'mass_assess_filename',
            'mass_do', 'mass_tp', 'mass_YS', 'mass_TS',
            'mass_depth_tol', 'mass_length_tol', 'mass_depth_cr', 'mass_length_cr',
            'mass_start_year', 'mass_verified'
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
        uploaded_file = st.file_uploader("Excel file", type=["xlsx", "xls"], key="upload_flow", label_visibility="collapsed")
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
                    depth_cr = st.number_input("Depth CR (mm/yr)", min_value=0.0, value=4.0, step=0.1, key="mass_depth_cr")
                    length_cr = st.number_input("Length CR (mm/yr)", min_value=0.0, value=25.0, step=1.0, key="mass_length_cr")
                    start_year = st.number_input("ILI Run Year", min_value=1900, max_value=2100, value=datetime.now().year, key="mass_start_year")
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
                            data = {
                                "do": do, "tp": tp, "YS": YS, "TS": TS,
                                "depth_tolerance": depth_tol, "length_tolerance": length_tol,
                                "depth_cr": depth_cr, "length_cr": length_cr, "start_year": int(start_year)
                            }
                            with httpx.Client(timeout=600.0) as client:
                                response = client.post(f"{BACKEND_URL}/api/pipeline/metal-loss/mass-assess", files=files, data=data)
                            if response.status_code == 200:
                                st.session_state['mass_assess_result'] = response.content
                                st.session_state['mass_assess_filename'] = f"Mass_Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d')}.xlsx"
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
    
        The tool uses **Modified B31G** to compute failure pressure (Pf) for each defect at each year.
    
        #### Step 1: Apply Tolerances
        ```
        dimp_0 = (depth_percent + depth_tolerance) × 0.01 × tp   [mm]
        Limp_0 = length_raw + length_tolerance                    [mm]
        ```
    
        #### Step 2: Defect Growth (per year i = 0 to 9)
        ```
        dimp_t = dimp_0 + (i × depth_cr)    [mm]
        Limp_t = Limp_0 + (i × length_cr)   [mm]
        ```
    
        #### Step 3: Normalized Parameters
        ```
        z = L² / (do × tp)     (defect length factor)
        d/t = dimp / tp        (depth ratio)
        ```
    
        #### Step 4: Flow Stress & Folias Factor
        ```
        Sflow = YS + 69 MPa
        ```
        - **If z ≤ 50**:  M = √(1 + 0.6275z - 0.003375z²)
        - **If z > 50**:  M = 0.032z + 3.3
    
        #### Step 5: Remaining Strength & Failure Pressure
        ```
        Rs = (1 - 0.85×d/t) / (1 - 0.85×d/t / M)
        Po = 2 × Sflow / (do/tp)
        Pf = Po × Rs × 1000  [kPa]  →  Pf_psi = Pf × 0.14503774
        ```
    
        #### Step 6: >80% Limit
        When **dimp/tp > 0.80**, the result shows **">80% leak"** (beyond B31G applicability).
    
        ---
        *Full documentation: `docs/functions/METAL_LOSS_MASS_ASSESSMENT.md`*
        """)

    # Help section
    with st.expander("ℹ️ Help & Instructions"):
        st.markdown("""
        **Step 1 – Upload:** Excel file with depth and length columns (e.g. `depth`, `Depth (%)`, `length`, `Length (mm)`).

        **Step 2 – Calculate:** Open Parameters to set pipe specs, tolerances, and corrosion rates, then click Run.

        **Step 3 – Download:** After the run completes, download the results Excel with 10 years of Pf (psi) per feature.

        **Note:** If depth exceeds 80% wall thickness in a year, that cell shows `>80% leak`.
        """)

    # Footer
    st.divider()
    st.caption("Metal Loss Mass Assessment Tool v1.0 | Chen's Engineer Toolbox")

with right_col:
    render_chat_expander(right_col, chat_visible)
