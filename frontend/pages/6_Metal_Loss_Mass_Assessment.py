import sys
from pathlib import Path
from datetime import datetime
import io
import httpx
import streamlit as st
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    set_page_config,
    BACKEND_URL,
)

# Page configuration
set_page_config("Metal Loss Mass Assessment", "📉")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

# Header
display_header(
    "📉 Metal Loss Mass Assessment",
    "Bulk assess metal loss features from Excel for 10-year pressure decay",
)

# Check backend status
if not check_backend_health():
    st.error(
        """
        ⚠️ **Backend API is not available**
        
        Please start the backend server:
        ```bash
        uv run uvicorn backend.main:app --reload
        ```
        """
    )
    st.stop()

st.info("📋 **About This Tool**: Upload an Excel file containing metal loss features (depth, length) to calculate the 10-year failure pressure decay for all features at once.")

# Main content area
st.subheader("📝 Assessment Parameters")

# Reset button
if st.button("🔄 Reset Tool", help="Clear all inputs and results"):
    keys_to_clear = ['mass_assess_result', 'mass_assess_filename']
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

col1, col2 = st.columns(2)

with col1:
    st.markdown("### Pipe Properties")
    do = st.number_input("Outside Diameter (mm)", min_value=0.0, value=273.1, step=0.1)
    tp = st.number_input("Wall Thickness (mm)", min_value=0.0, value=9.27, step=0.01)
    YS = st.number_input("Yield Strength (MPa)", min_value=0.0, value=359.0, step=1.0)
    TS = st.number_input("Tensile Strength (MPa)", min_value=0.0, value=455.0, step=1.0)

with col2:
    st.markdown("### ILI & Growth Parameters")
    depth_tol = st.number_input("Depth Tolerance (%)", min_value=0.0, value=10.0, step=0.1)
    length_tol = st.number_input("Length Tolerance (mm)", min_value=0.0, value=0.0, step=1.0)
    depth_cr = st.number_input("Depth Corrosion Rate (mm/yr)", min_value=0.0, value=4.0, step=0.1, help="Default: 4.0 mm/year")
    length_cr = st.number_input("Length Corrosion Rate (mm/yr)", min_value=0.0, value=25.0, step=1.0, help="Default: 25.0 mm/year")
    start_year = st.number_input("ILI Run Year", min_value=1900, max_value=2100, value=datetime.now().year)

st.markdown("---")
st.subheader("📁 Upload Data")
uploaded_file = st.file_uploader("Choose an Excel file", type=["xlsx", "xls"])

if uploaded_file:
    st.success(f"File '{uploaded_file.name}' uploaded successfully!")
    
    if st.button("🚀 Run Mass Assessment", type="primary", use_container_width=True):
        with st.spinner("⏳ Processing features... This may take a moment for large files."):
            try:
                # Prepare files and data
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {
                    "do": do,
                    "tp": tp,
                    "YS": YS,
                    "TS": TS,
                    "depth_tolerance": depth_tol,
                    "length_tolerance": length_tol,
                    "depth_cr": depth_cr,
                    "length_cr": length_cr,
                    "start_year": int(start_year)
                }
                
                # Call the API
                with httpx.Client(timeout=600.0) as client:
                    response = client.post(
                        f"{BACKEND_URL}/api/pipeline/metal-loss/mass-assess",
                        files=files,
                        data=data,
                    )
                
                if response.status_code == 200:
                    st.session_state['mass_assess_result'] = response.content
                    st.session_state['mass_assess_filename'] = f"Mass_Metal_Loss_Assessment_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    st.success("✅ Mass assessment completed successfully!")
                else:
                    try:
                        error_detail = response.json().get("detail", "Unknown error")
                    except:
                        error_detail = response.text
                    st.error(f"❌ Error processing assessment: {error_detail}")
                    
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

    # Show download button if result is in session state
    if 'mass_assess_result' in st.session_state:
        st.markdown("---")
        st.subheader("📥 Results")
        st.download_button(
            label="💾 Download Assessment Results (.xlsx)",
            data=st.session_state['mass_assess_result'],
            file_name=st.session_state['mass_assess_filename'],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="download_mass_assess"
        )
        st.info("💡 The results will stay here until you click 'Reset Tool' or refresh the page manually.")

# Help section
with st.expander("ℹ️ Help & Instructions"):
    st.markdown("""
    ### How to use this tool:
    1. **Input Pipe Properties**: Enter the outside diameter, wall thickness, and material strengths.
    2. **Set Tolerances and Growth Rates**: 
       - **Depth Tolerance**: Tool accuracy for depth (usually 10% WT).
       - **Length Tolerance**: Tool accuracy for length (usually 0 mm).
       - **Corrosion Rates**: The annual growth of the defect in depth and length.
    3. **Upload Excel**: Your Excel file should have columns named like **'depth'** (or 'defect depth') and **'length'** (or 'defect length').
    4. **Run Assessment**: The tool will generate 10 new columns (one for each year) with the calculated failure pressure (Pf) in psi.
    5. **Leak Warning**: If a defect's depth exceeds 80% of the wall thickness in a given year, the result will show **'>80% leak'**.
    """)

# Footer
st.divider()
st.caption("Metal Loss Mass Assessment Tool v1.0 | Chen's Engineer Toolbox")
