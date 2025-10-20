import sys
from pathlib import Path

import httpx
import streamlit as st

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_sidebar_navigation,
    set_page_config,
)

# Page configuration
set_page_config("TML Data Loader", "⚙️")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

# Header
display_header(
    "⚙️ TML Data Loader",
    "Process Thickness Monitoring Location (TML) data with customizable workflows",
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

# Privacy notice
st.info("🔒 **Privacy Notice:** Your files are processed in memory only and are not stored on the server after processing.")

# File upload section
st.subheader("📁 Upload Files")
col1, col2 = st.columns(2)

with col1:
    source_file = st.file_uploader(
        "Source Excel File (input.xlsx)",
        type=["xlsx", "xls"],
        help="Upload the source data file containing TML information"
    )

with col2:
    template_file = st.file_uploader(
        "Template Excel File (TM_Loader.xlsx)",
        type=["xlsx", "xls"],
        help="Upload the template file with Assets and TML sheets"
    )

# Workflow selection section
st.subheader("🔧 Select Workflows to Process")

# Define all 20 workflows with their descriptions
workflows = {
    1: "Sub-CML Status (deactivated)",
    2: "AER Flag",
    3: "Code Year T-Min Formula",
    4: "Design Code",
    5: "Material Specification",
    6: "Material Grade",
    7: "Design Temperature",
    8: "Piping Formula",
    9: "Outside Diameter (OD)",
    10: "NPS (Nominal Pipe Size)",
    11: "Schedule",
    12: "Design Pressure",
    13: "Temperature Coefficient",
    14: "Tnom (Nominal Thickness)",
    15: "Tmin (Minimum Thickness)",
    16: "Override Allowable Stress",
    17: "Allowable Stress",
    18: "Design Factor",
    19: "Joint Factor",
    20: "Location Factor",
}

# Create checkboxes in a 4-column grid
st.write("Select the workflows you want to process:")

# Select all / Deselect all buttons
col_select_1, col_select_2, col_select_3 = st.columns([1, 1, 8])
with col_select_1:
    if st.button("✅ Select All"):
        for i in range(1, 21):
            st.session_state[f"workflow_{i}"] = True
        st.rerun()

with col_select_2:
    if st.button("⬜ Deselect All"):
        for i in range(1, 21):
            st.session_state[f"workflow_{i}"] = False
        st.rerun()

st.write("")  # Add spacing

# Create 5 rows with 4 columns each for the 20 workflows
for row in range(5):
    cols = st.columns(4)
    for col_idx in range(4):
        workflow_id = row * 4 + col_idx + 1
        with cols[col_idx]:
            # Initialize session state if not exists
            if f"workflow_{workflow_id}" not in st.session_state:
                st.session_state[f"workflow_{workflow_id}"] = False
            
            st.checkbox(
                f"**{workflow_id:02d}**: {workflows[workflow_id]}",
                key=f"workflow_{workflow_id}",
            )

# Get selected workflows
selected_workflows = [i for i in range(1, 21) if st.session_state.get(f"workflow_{i}", False)]

# Show selected count
if selected_workflows:
    st.success(f"✅ Selected {len(selected_workflows)} workflow(s)")
else:
    st.warning("⚠️ No workflows selected. Please select at least one workflow to process.")

# Process button
st.write("")  # Add spacing
process_button = st.button(
    "🚀 Process TML Data",
    type="primary",
    disabled=not (source_file and template_file and selected_workflows),
    use_container_width=True
)

if process_button:
    if not source_file or not template_file:
        st.error("❌ Please upload both source and template files")
    elif not selected_workflows:
        st.error("❌ Please select at least one workflow to process")
    else:
        # Process the data
        with st.spinner("⏳ Processing TML data... This may take a few moments."):
            try:
                # Prepare the request
                files = {
                    "source_file": (source_file.name, source_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                    "template_file": (template_file.name, template_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
                }
                
                data = {
                    "workflows": ",".join(map(str, selected_workflows))
                }
                
                # Call the API
                with httpx.Client(timeout=300.0) as client:  # 5 minute timeout for large files
                    response = client.post(
                        "http://localhost:8000/api/tml/process",
                        files=files,
                        data=data,
                    )
                
                if response.status_code == 200:
                    st.success("✅ Processing completed successfully!")
                    
                    # Provide download button
                    st.download_button(
                        label="📥 Download Output Files (ZIP)",
                        data=response.content,
                        file_name="TML_Output.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
                    
                    # Show summary
                    st.info(
                        f"""
                        **Processing Summary:**
                        - Source file: `{source_file.name}`
                        - Template file: `{template_file.name}`
                        - Workflows processed: {len(selected_workflows)}
                        - Output files: {len(selected_workflows)} Excel files
                        
                        The ZIP file contains all generated output files. Extract the ZIP to access individual files.
                        """
                    )
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    st.error(f"❌ Error processing data: {error_detail}")
                    
            except httpx.TimeoutException:
                st.error("❌ Request timed out. The file might be too large or the server is busy.")
            except httpx.ConnectError:
                st.error("❌ Could not connect to the backend server. Please make sure it's running.")
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

# Help section
with st.expander("ℹ️ Help & Information"):
    st.markdown("""
    ### How to Use This Tool
    
    1. **Upload Files:**
       - **Source File**: Contains the raw TML data with fields to be updated
       - **Template File**: Contains the base template structure with Assets and TML sheets
    
    2. **Select Workflows:**
       - Choose which parameters you want to process
       - You can select multiple workflows at once
       - Use "Select All" to choose all workflows or "Deselect All" to clear your selection
    
    3. **Process Data:**
       - Click the "Process TML Data" button
       - Wait for processing to complete (may take 30 seconds to a few minutes depending on data size)
       - Download the generated ZIP file containing all output files
    
    ### Available Workflows
    
    Each workflow processes a specific TML parameter:
    - **01-02**: Status and flag updates
    - **03-06**: Code and material specifications
    - **07-12**: Design parameters (temperature, pressure, dimensions)
    - **13-20**: Advanced parameters (coefficients, factors, stresses)
    
    ### Output Files
    
    Each selected workflow generates a separate Excel file with the naming format:
    - `XX_TM_Loader_[Parameter].xlsx` (where XX is the workflow number)
    
    All files are packaged into a single ZIP file for download.
    
    ### File Requirements
    
    **Source File** must contain:
    - Sheet named "Source_Data"
    - Column "AER_Status_CML" (records with "Yes" will be processed)
    - Relevant columns for selected workflows
    
    **Template File** must contain:
    - Sheet named "Assets"
    - Sheet named "TML"
    
    ### Notes
    - Maximum file size: 30 MB per file
    - Supported formats: .xlsx, .xls
    - Files are processed in memory and not stored permanently
    - Processing time depends on file size and number of workflows selected
    """)

# Footer
st.divider()
st.caption("TML Data Loader v1.0 | Chen's Engineer Toolbox")

