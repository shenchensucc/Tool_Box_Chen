"""
Dig Package Generator Page

Upload MDL, ILI data, and template files to generate dig packages.
"""

import sys
from pathlib import Path

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
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

# Page configuration
set_page_config("Dig Package Generator", "📦")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

main = get_layout_main()

with main:
    # Header
    display_header(
        "📦 Dig Package Generator",
        "Generate dig package Excel and PDF files from MDL, ILI data, and template",
    )

    # Check backend status
    if not check_backend_health():
            show_backend_unavailable_and_retry()
            st.stop()

        # Initialize session state
    if "dig_packages_generated" not in st.session_state:
        st.session_state.dig_packages_generated = False

    # Information section
    st.info(
        """
        📋 **About This Tool**: Generate dig package files from three source files:
        - **MDL (Master Dig List)**: Contains dig IDs and target features
        - **ILI Data**: In-line inspection data with detailed feature information
        - **Template**: Fillable Excel template for dig packages
    
        The tool will match features, populate templates, and generate Excel + PDF files for each dig ID.
        """
    )

    # Main content
    st.markdown("### 📁 Step 1: Upload Source Files")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**MDL File**")
        mdl_file = st.file_uploader(
            "Master Dig List (.xlsx)",
            type=["xlsx"],
            help="Excel file containing dig IDs and target features",
            key="mdl_file",
        )
        if mdl_file:
            st.success(f"✅ {mdl_file.name}")

    with col2:
        st.markdown("**Template File**")
        template_file = st.file_uploader(
            "Dig Package Template (.xlsx)",
            type=["xlsx"],
            help="Excel template file with named ranges",
            key="template_file",
        )
        if template_file:
            st.success(f"✅ {template_file.name}")

    st.markdown("### 📊 Step 2: Upload ILI Data Files")
    st.info("💡 You can upload multiple ILI files in different formats (TDW, Rosen-MFLA, Rosen-MFLC, Rosen-EMAT).")

    if "ili_files_data" not in st.session_state:
        st.session_state.ili_files_data = []

    # Multiple ILI uploader
    uploaded_ili_files = st.file_uploader(
        "Upload ILI Data Files (.xlsx)",
        type=["xlsx"],
        accept_multiple_files=True,
        help="Excel files containing in-line inspection data",
        key="ili_files_uploader"
    )

    if uploaded_ili_files:
        # Create a list to store file info and selected format
        new_ili_data = []
    
        for i, file in enumerate(uploaded_ili_files):
            st.markdown(f"**File {i+1}:** `{file.name}`")
            cols = st.columns([2, 3])
            with cols[0]:
                # Try to guess format from filename
                default_index = 0
                fname_lower = file.name.lower()
                if "tdw" in fname_lower: default_index = 0
                elif "mfla" in fname_lower: default_index = 1
                elif "mflc" in fname_lower: default_index = 2
                elif "emat" in fname_lower: default_index = 3
            
                format_choice = st.selectbox(
                    f"Select format for {file.name}",
                    options=["TDW", "Rosen-MFLA", "Rosen-MFLC", "Rosen-EMAT"],
                    index=default_index,
                    key=f"format_{i}"
                )
        
            new_ili_data.append({
                "file": file,
                "format": format_choice
            })
    
        st.session_state.ili_files_data = new_ili_data

    # Revision number input
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

    # Generate button
    st.markdown("---")
    st.markdown("### 🚀 Step 4: Generate Dig Packages")

    # Check if all files are uploaded
    all_files_uploaded = mdl_file is not None and len(st.session_state.ili_files_data) > 0 and template_file is not None

    if not all_files_uploaded:
        st.warning("⚠️ Please upload MDL, at least one ILI file, and a Template before generating dig packages.")

    if st.button(
        "🚀 Generate Dig Packages",
        type="primary",
        disabled=not all_files_uploaded,
    ):
        with st.spinner("⏳ Generating dig packages... This may take a few minutes."):
            try:
                # Prepare files for upload
                files = [
                    ("mdl_file", (mdl_file.name, mdl_file.getvalue(), mdl_file.type)),
                    ("template_file", (template_file.name, template_file.getvalue(), template_file.type)),
                ]
            
                # Add all ILI files
                ili_formats = []
                for i, item in enumerate(st.session_state.ili_files_data):
                    files.append(("ili_files", (item["file"].name, item["file"].getvalue(), item["file"].type)))
                    ili_formats.append(item["format"])
            
                data = {
                    "revision": revision,
                    "ili_formats": ",".join(ili_formats)
                }
            
                # Call API
                with httpx.Client(timeout=600.0) as client:  # 10 minute timeout for large files
                    response = client.post(
                        f"{BACKEND_URL}/api/pipeline/dig-package/generate",
                        files=files,
                        data=data,
                    )
            
                if response.status_code == 200:
                    # Store the ZIP file in session state
                    st.session_state.dig_packages_zip = response.content
                
                    # Get filename from header or use default
                    disp = response.headers.get("Content-Disposition", "")
                    if "filename=" in disp:
                        st.session_state.dig_packages_filename = disp.split("filename=")[-1].strip('"')
                    else:
                        st.session_state.dig_packages_filename = f"Dig_Packages_R{revision}.zip"
                    
                    st.session_state.dig_packages_generated = True
                    st.success("✅ Dig packages generated successfully!")
                    st.rerun()
            
                else:
                    try:
                        error_detail = response.json().get("detail", "Unknown error")
                    except:
                        error_detail = f"Server error ({response.status_code})"
                    st.error(f"❌ Error generating dig packages: {error_detail}")
        
            except httpx.TimeoutException:
                st.error("❌ Request timed out. The files might be too large or processing is taking too long.")
            except httpx.ConnectError:
                st.error("❌ Could not connect to the backend server. Please make sure it's running.")
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

    # Download section
    if st.session_state.dig_packages_generated:
        st.markdown("---")
        st.markdown("### 📥 Step 4: Download Results")
    
        st.success(
            """
            ✅ **Dig packages are ready!**
        
            The ZIP file contains Excel and PDF files for each dig ID found in the MDL.
            Click the button below to download.
            """
        )
    
        st.download_button(
            label="💾 Download Dig Packages (ZIP)",
            data=st.session_state.dig_packages_zip,
            file_name=st.session_state.dig_packages_filename,
            mime="application/zip",
            width="stretch",
            type="primary",
        )
    
        # Clear button
        if st.button("🔄 Generate New Batch", width="stretch"):
            st.session_state.dig_packages_generated = False
            st.rerun()

    # Help section
    with st.expander("ℹ️ Help & Requirements"):
        st.markdown(
            """
            ### File Requirements
        
            **MDL (Master Dig List)** must contain:
            - Dig ID column (must contain "GW" in the ID)
            - Feature information (ID, Length, Width)
            - Pipe properties (OD, NWT, Grade, Year, MOP, SEP, etc.)
            - Assessment/Exposure information
            - Location data (Latitude, Longitude, Milepost)
        
            **ILI Data** must contain:
            - Feature ID or dimensions for matching
            - Feature properties (Type, Description, Depth, Length, Width, Orientation)
            - ILI Chainage for positioning
            - Joint Number for range filtering
        
            **Template** must have:
            - Named ranges for single-value fields (e.g., `tmp_DigID_`, `tmp_pipeOD`)
            - Named range `tmp_feaIDs_row` for feature table starting position
            - Named ranges for excavation summary sections
        
            ### Feature Matching Logic
        
            The tool uses two methods to match MDL target features with ILI features:
        
            1. **Feature ID Matching** (Primary): Direct match by Feature ID
            2. **Dimension Matching** (Fallback): Match by Length and Width (rounded to 3 decimals)
        
            Target features will be highlighted in **bold, red text with grey background**.
        
            ### Output Structure
        
            For each dig ID in the MDL, two files will be generated:
            - `{{Dig Name or Dig ID}}_DP_R{revision}.xlsx` - Excel dig package
            - Same stem `.pdf` - PDF version (if available)
        
            All files are packaged in a single ZIP file for download.
        
            ### Named Ranges in Template
        
            The template must define these named ranges (among others):
            - `tmp_DigID_` - Dig ID
            - `tmp_revNum` - Revision number
            - `tmp_pipNme` - Pipeline name
            - `tmp_pipeOD`, `tmp_pipeNWT` - Pipe dimensions
            - `tmp_mop`, `tmp_sep` - Pressure values
            - `tmp_Lat`, `tmp_Lon` - Coordinates
            - `tmp_feaIDs_row` - Feature table start row
            - `tmp_numExv_num`, `tmp_numExp_num` - Summary sections
        
            To view named ranges in Excel: **Formulas** tab → **Name Manager**
        
            ### Troubleshooting
        
            - **No dig packages generated**: Check that MDL has valid Dig IDs (containing "GW")
            - **Features not matching**: Verify Feature IDs or dimensions match between MDL and ILI
            - **Template errors**: Ensure all required named ranges are defined in template
            - **Large files**: Processing may take several minutes for large datasets
            """
        )

    # Footer
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
