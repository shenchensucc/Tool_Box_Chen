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
    set_page_config,
    show_backend_unavailable_and_retry,
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
    show_backend_unavailable_and_retry()
    st.stop()

# Privacy notice
st.info("🔒 **Privacy Notice:** Your files are processed in memory only and are not stored on the server after processing.")


# Cached function for template fetching
@st.cache_data(ttl=300)  # Cache for 5 minutes
def fetch_template(template_type: str):
    """Fetch template from backend and cache for better performance"""
    try:
        response = httpx.get(
            f"{BACKEND_URL}/api/tml/download-template/{template_type}",
            timeout=10.0
        )
        if response.status_code == 200:
            return {"success": True, "content": response.content}
        else:
            return {"success": False, "content": None}
    except Exception as e:
        return {"success": False, "content": None, "error": str(e)}

# Template download section
st.subheader("📥 Download Blank Templates")
st.write("Download template files to help you prepare your data correctly:")

col_t1, col_t2 = st.columns(2)

with col_t1:
    template_result = fetch_template("source")
    if template_result["success"]:
        st.download_button(
            label="📄 Download Source Data Template",
            data=template_result["content"],
            file_name="Source_Data_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Download a blank template for preparing your source data"
        )
    else:
        st.warning("⚠️ Source template not available. Please ensure backend is running and template file is placed in backend/static/templates/tml/")

with col_t2:
    template_result = fetch_template("tm_loader")
    if template_result["success"]:
        st.download_button(
            label="📄 Download TM_Loader Template",
            data=template_result["content"],
            file_name="TM_Loader_Template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            help="Download a blank TM_Loader template file"
        )
    else:
        st.warning("⚠️ TM_Loader template not available. Please ensure backend is running and template file is placed in backend/static/templates/tml/")

st.divider()

# Initialize session state for processing results
if 'tml_processing_result' not in st.session_state:
    st.session_state.tml_processing_result = None

# File upload section
st.subheader("📁 Upload Files")
col1, col2 = st.columns(2)

with col1:
    source_file = st.file_uploader(
        "Source Excel File (input.xlsx)",
        type=["xlsx", "xls"],
        help="Upload the source data file containing TML information",
        on_change=lambda: st.session_state.update({'tml_processing_result': None})
    )

with col2:
    template_file = st.file_uploader(
        "Template Excel File (TM_Loader.xlsx)",
        type=["xlsx", "xls"],
        help="Upload the template file with Assets and TML sheets",
        on_change=lambda: st.session_state.update({'tml_processing_result': None})
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


# Fragment for workflow selection to prevent full page reloads
@st.fragment
def render_workflow_selection():
    """Render workflow selection checkboxes with optimized performance"""
    
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
    selected = [i for i in range(1, 21) if st.session_state.get(f"workflow_{i}", False)]
    
    # Show selected count
    if selected:
        st.success(f"✅ Selected {len(selected)} workflow(s)")
    else:
        st.warning("⚠️ No workflows selected. Please select at least one workflow to process.")
    
    return selected


# Render workflow selection and get selected workflows
selected_workflows = render_workflow_selection()

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
                        f"{BACKEND_URL}/api/tml/process",
                        files=files,
                        data=data,
                    )
                
                if response.status_code == 200:
                    # Parse response JSON
                    result = response.json()
                    zip_token = result.get("zip_token")
                    combined_token = result.get("combined_token")
                    
                    # Immediately fetch the files and store in session state
                    zip_data = None
                    combined_data = None
                    
                    try:
                        # Download ZIP file immediately
                        zip_response = httpx.get(
                            f"{BACKEND_URL}/api/tml/download/{zip_token}",
                            timeout=60.0
                        )
                        if zip_response.status_code == 200:
                            zip_data = zip_response.content
                    except Exception as e:
                        print(f"Error fetching ZIP: {e}")
                    
                    try:
                        # Download combined file immediately
                        combined_response = httpx.get(
                            f"{BACKEND_URL}/api/tml/download/{combined_token}",
                            timeout=60.0
                        )
                        if combined_response.status_code == 200:
                            combined_data = combined_response.content
                    except Exception as e:
                        print(f"Error fetching combined file: {e}")
                    
                    # Store result and file data in session state
                    st.session_state.tml_processing_result = {
                        'result': result,
                        'source_filename': source_file.name,
                        'template_filename': template_file.name,
                        'zip_data': zip_data,
                        'combined_data': combined_data
                    }
                    
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    st.error(f"❌ Error processing data: {error_detail}")
                    
            except httpx.TimeoutException:
                st.error("❌ Request timed out. The file might be too large or the server is busy.")
            except httpx.ConnectError:
                st.error("❌ Could not connect to the backend server. Please make sure it's running.")
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")

# Display results if available in session state
if st.session_state.tml_processing_result:
    result_data = st.session_state.tml_processing_result
    result = result_data['result']
    zip_token = result.get("zip_token")
    combined_token = result.get("combined_token")
    workflows_processed = result.get("workflows_processed", 0)
    workflow_summary = result.get("workflow_summary", {})
    
    st.success("✅ Processing completed successfully!")
    
    # Show summary
    st.info(
        f"""
        **Processing Summary:**
        - Source file: `{result_data['source_filename']}`
        - Template file: `{result_data['template_filename']}`
        - Workflows processed: {workflows_processed}
        - Output files generated: {workflows_processed} Excel files
        
        Choose your preferred download format below.
        """
    )
    
    # Display workflow summary table
    if workflow_summary:
        st.subheader("📊 Workflow Processing Details")
        
        # Define workflow names
        workflow_names = {
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
        
        # Create summary table data
        summary_data = []
        for workflow_id, records_count in sorted(workflow_summary.items()):
            # Convert workflow_id to int (comes as string from JSON)
            workflow_id_int = int(workflow_id)
            workflow_name = workflow_names.get(workflow_id_int, f"Workflow {workflow_id}")
            status = "✅ Processed" if records_count > 0 else "⚠️ No records"
            summary_data.append({
                "Workflow ID": f"{workflow_id_int:02d}",
                "Parameter": workflow_name,
                "Records Found": records_count,
                "Status": status
            })
        
        # Display as dataframe
        import pandas as pd
        summary_df = pd.DataFrame(summary_data)
        st.dataframe(
            summary_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Show totals
        total_records = sum(workflow_summary.values())
        workflows_with_data = sum(1 for count in workflow_summary.values() if count > 0)
        
        col_stat1, col_stat2, col_stat3 = st.columns(3)
        with col_stat1:
            st.metric("Total Records Processed", f"{total_records:,}")
        with col_stat2:
            st.metric("Workflows with Data", f"{workflows_with_data}/{len(workflow_summary)}")
        with col_stat3:
            st.metric("Workflows Skipped", f"{len(workflow_summary) - workflows_with_data}")
        
        st.write("")  # Add spacing
    
    # Two download buttons side by side
    col_dl1, col_dl2 = st.columns(2)
    
    # Get cached file data from session state
    zip_data = result_data.get('zip_data')
    combined_data = result_data.get('combined_data')
    
    with col_dl1:
        # Download ZIP file
        if zip_data:
            st.download_button(
                label="📦 Download Separate Files (ZIP)",
                data=zip_data,
                file_name="TML_Output.zip",
                mime="application/zip",
                use_container_width=True,
                help="Download a ZIP file containing separate Excel files for each workflow",
                key="download_zip_btn"
            )
        else:
            st.error("❌ ZIP file not available. Please process the data again.")
    
    with col_dl2:
        # Download combined file
        if combined_data:
            st.download_button(
                label="📊 Download Combined File (XLSX)",
                data=combined_data,
                file_name="TML_Combined_Output.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                help="Download a single Excel file with all workflow data combined",
                key="download_combined_btn"
            )
        else:
            st.error("❌ Combined file not available. Please process the data again.")
    
    # Additional info
    st.write("")
    st.caption("""
    **Download Options:**
    - **Separate Files (ZIP)**: Contains individual Excel files for each workflow - use this if you need to upload each workflow separately to your system
    - **Combined File (XLSX)**: Contains all workflow data in one Excel file with Assets and TML sheets - use this for a consolidated view or single import
    """)

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
    
    ---
    
    ### 📋 Required File Format
    
    #### **Source File Requirements**
    
    **Must-Have Structure:**
    - ✅ **Sheet Name**: Must have a sheet named `"Source_Data"`
    - ✅ **Required Core Columns** (present in ALL workflows):
      - `Equipment ID` - Equipment identifier (preserved with leading zeros)
      - `CML Group ID` - CML Group identifier
      - `sub-CML ID` - Sub-CML identifier
      - `AER_Status_CML` - **CRITICAL**: Only records containing "Yes" will be processed
    
    **Workflow-Specific Columns** (required based on selected workflows):
    
    | Workflow # | Workflow Name | Required Column(s) | Filter Logic |
    |:-----------|:--------------|:-------------------|:-------------|
    | **01** | Status | `AER_Status_CML` | Must contain "To be de-active" |
    | **02** | AER Flag | `AER_Status_CML` | Must contain "Yes" |
    | **03** | Code Year T-Min | `Code Year (T-Min Formula)` | Non-empty values |
    | **04** | Design Code | `CorrValue_Design_Code` | Non-empty & non-zero |
    | **05** | Material Spec | `CorrValue_Material` | Non-empty & non-zero |
    | **06** | Material Grade | `CorrValue_Grade` | Non-empty & non-zero |
    | **07** | Design Temperature | `CorrValue_T` | Non-empty & non-zero |
    | **08** | Piping Formula | `Piping Formula` | Non-empty values |
    | **09** | Outside Diameter | `CorrValue_OD` | Non-empty & non-zero |
    | **10** | NPS | `CorrValue_NPS` | Non-empty & non-zero |
    | **11** | Schedule | `CorrValue_Schedule` | Non-empty & non-zero |
    | **12** | Design Pressure | `CorrValue_P` | Non-empty & non-zero |
    | **13** | Temp Coefficient | `Temperature Coefficient` | Non-empty values |
    | **14** | Tnom | `CorrValue_Tnom` | Non-empty & non-zero |
    | **15** | Tmin | `CorrValue_Tmin` | Non-empty & non-zero |
    | **16** | Override Allowable Stress | `Override Allowable Stress` | Non-empty values |
    | **17** | Allowable Stress | `AER_SMYS` | Processes ALL values |
    | **18** | Design Factor | `Design Factor` | Non-empty values |
    | **19** | Joint Factor | `Joint Factor` | Non-empty values |
    | **20** | Location Factor | `CorrValue_LocFactor` | Non-empty & non-zero |
    
    #### **Template File Requirements**
    
    **Must-Have Structure:**
    - ✅ **Sheet Name**: Must have sheets named `"Assets"` and `"TML"`
    - ✅ **Purpose**: Provides the base structure that will be populated with processed data
    - ✅ **Columns**: The tool will automatically map source columns to template columns
    
    ---
    
    ### ⚙️ How the Tool Processes Data
    
    1. **Initial Filtering**: 
       - Reads `Source_Data` sheet from source file
       - **Filters to only process records where `AER_Status_CML` contains "Yes"**
       - If no "Yes" records found, processing will fail with an error message
    
    2. **Workflow-Specific Filtering**:
       - Each workflow applies additional filters based on its required column
       - Empty values (NaN) are skipped
       - Zero values are skipped (for numeric fields marked "non-zero")
       - Only valid records are processed and added to output
    
    3. **Data Mapping**:
       - Source columns are renamed to match template structure
       - Example: `CML Group ID` → `TML Group ID`, `sub-CML ID` → `TML_ID`
       - Adds system columns: `CMMS System = "P1R-100"`, `TML Analysis Type = "TML"`
    
    4. **Output Generation**:
       - Template data is copied to output file
       - Processed source data is appended to both `Assets` and `TML` sheets
       - Duplicates in Assets are removed automatically
       - Column widths are set to 20 for readability
    
    ---
    
    ### ❌ What Happens if Columns are Missing?
    
    **Scenario 1: Missing Core Columns**
    - If `Equipment ID`, `CML Group ID`, or `sub-CML ID` is missing:
      - ❌ **Workflow will fail** with a "KeyError" indicating the missing column
    
    **Scenario 2: Missing `AER_Status_CML`**
    - ❌ **Processing will fail immediately** with error message:
      - *"Source file missing required column 'AER_Status_CML'"*
    
    **Scenario 3: Missing Workflow-Specific Column**
    - If a selected workflow's required column is missing:
      - ❌ **That workflow will fail**, but other workflows continue
      - Error logged showing which column is missing
    
    **Scenario 4: All Values Filtered Out**
    - If column exists but all values are empty/zero/don't match filter:
      - ⚠️ **Workflow completes but outputs empty results**
      - Message: "No records found matching the criteria"
      - Output file still generated with template structure only
    
    **Scenario 5: No "Yes" in `AER_Status_CML`**
    - ❌ **All processing stops** with error:
      - *"No records found with AER_Status_CML containing 'Yes'"*
    
    ---
    
    ### 📦 Output Files
    
    Each selected workflow generates a separate Excel file:
    - **Naming Format**: `XX_TM_Loader_[Parameter].xlsx` (XX = workflow number)
    - **Contains**: Two sheets - `Assets` and `TML` with processed data
    - **Special Case**: Workflow 17 generates TWO files:
      - `17_TM_Loader_AllowableStress.xlsx` (filtered: non-zero values only)
      - `17_TM_Loader_AllowableStress_All.xlsx` (all values including zeros)
    
    All files are packaged into **`TML_Output.zip`** for download.
    
    ---
    
    ### 📌 Important Notes
    
    - **Maximum file size**: 100 MB per file
    - **Supported formats**: .xlsx, .xls
    - **Data Privacy**: Files are processed in memory only and deleted immediately after processing
    - **Processing time**: 30 seconds to a few minutes (depends on file size and workflow count)
    - **Column Names**: Must match exactly (case-sensitive)
    - **Equipment ID**: Leading zeros are preserved (e.g., "00123" stays as "00123")
    - **Error Handling**: If one workflow fails, others continue processing
    
    ---
    
    ### 💡 Tips for Success
    
    ✅ **Before uploading**, verify:
    1. Source file has sheet named "Source_Data" (exact spelling)
    2. Template file has sheets "Assets" and "TML"
    3. All required columns exist with exact names (case-sensitive)
    4. `AER_Status_CML` column has at least some "Yes" values
    5. Selected workflows have their required columns populated with valid data
    
    ✅ **If you encounter errors**:
    1. Check error message for specific missing column names
    2. Verify sheet names are spelled correctly
    3. Ensure data types are correct (numeric for CorrValue fields)
    4. Check that you're not selecting workflows whose columns don't exist in your source
    """)

# Footer
st.divider()
st.caption("TML Data Loader v1.0 | Chen's Engineer Toolbox")

