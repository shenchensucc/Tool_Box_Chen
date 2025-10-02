import streamlit as st

from frontend_utils import apply_custom_styling, display_header, set_page_config

# Page configuration
set_page_config("Pipeline Tools - Chen's Toolbox", "🛢️")
apply_custom_styling()

# Header
display_header("🛢️ Pipeline Tools", "Tools for pipeline inspection and analysis")

# Main content
st.markdown(
    """
    Welcome to the **Pipeline Tools** section. This area provides comprehensive tools for 
    pipeline integrity management, inspection data analysis, and visualization.
    """
)

st.markdown("---")

# Available Tools Section
st.markdown("### 🔧 Available Pipeline Tools")

# ILI Visual Tool Card
col1, col2 = st.columns([2, 1])

with col1:
    st.markdown(
        """
        <div style='padding: 2rem; background: linear-gradient(135deg, rgba(102, 126, 234, 0.1) 0%, rgba(118, 75, 162, 0.1) 100%); 
                    border-radius: 12px; border-left: 4px solid #667eea; margin-bottom: 1rem;'>
            <h3 style='margin-top: 0;'>📊 ILI Visual Tool</h3>
            <p style='font-size: 1.1rem; margin-bottom: 1rem;'>
                Upload and analyze In-Line Inspection (ILI) data from Excel files. 
                Generate statistical summaries and interactive visualizations.
            </p>
            <p><strong>Features:</strong></p>
            <ul>
                <li>📁 Multi-sheet Excel file support</li>
                <li>🔍 Interactive data preview</li>
                <li>📈 Statistical analysis (mean, std, quartiles)</li>
                <li>📊 Distribution histograms</li>
                <li>🎯 Distance-based scatter plots</li>
                <li>📦 Box plots for outlier detection</li>
                <li>💾 CSV export functionality</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown("### Quick Access")
    if st.button("🚀 Open ILI Visual Tool", type="primary", use_container_width=True):
        st.switch_page("pages/4_ILI_Visual_Tool.py")

    st.info(
        """
        **Supported Files:**
        - Excel (.xlsx, .xls)
        - Max size: 10 MB
        
        **Data Types:**
        - Distance measurements
        - Depth readings
        - Metal loss percentages
        - Custom numeric columns
        """
    )

st.markdown("---")

# Coming Soon Section
st.markdown("### 🚧 Coming Soon")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        """
        <div style='padding: 1.5rem; border: 2px dashed rgba(102, 126, 234, 0.3); 
                    border-radius: 12px; text-align: center; height: 200px; display: flex; 
                    flex-direction: column; justify-content: center;'>
            <h4>🔄 Pipeline Integrity Manager</h4>
            <p style='color: #7f8c8d;'>Manage pipeline integrity data and assessments</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        """
        <div style='padding: 1.5rem; border: 2px dashed rgba(102, 126, 234, 0.3); 
                    border-radius: 12px; text-align: center; height: 200px; display: flex; 
                    flex-direction: column; justify-content: center;'>
            <h4>📋 Risk Assessment Tool</h4>
            <p style='color: #7f8c8d;'>Evaluate pipeline risks and prioritize actions</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col3:
    st.markdown(
        """
        <div style='padding: 1.5rem; border: 2px dashed rgba(102, 126, 234, 0.3); 
                    border-radius: 12px; text-align: center; height: 200px; display: flex; 
                    flex-direction: column; justify-content: center;'>
            <h4>📊 Trend Analysis</h4>
            <p style='color: #7f8c8d;'>Track pipeline conditions over time</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")

# Quick Guide Section
with st.expander("📖 Quick Guide - How to Use Pipeline Tools", expanded=False):
    st.markdown(
        """
        ### Getting Started with ILI Visual Tool
        
        1. **Prepare Your Data**
           - Ensure your Excel file contains ILI inspection data
           - Include columns for distance, depth, metal loss, or other metrics
           - Keep file size under 10 MB
        
        2. **Upload and Preview**
           - Navigate to the ILI Visual Tool
           - Upload your Excel file
           - Click "Preview" to see available sheets and columns
        
        3. **Map Your Columns**
           - Select the sheet containing your data
           - Map key columns (distance, depth, metal loss)
           - You can process any numeric columns
        
        4. **Analyze Results**
           - View statistical summaries
           - Explore interactive charts
           - Identify trends and anomalies
        
        5. **Export Data**
           - Download processed statistics as CSV
           - Use results for reporting or further analysis
        
        ### Tips for Best Results
        
        - **Clean Data**: Remove empty rows and ensure numeric columns contain only numbers
        - **Column Names**: Use clear, descriptive column headers
        - **Units**: Keep consistent units throughout your dataset
        - **Missing Data**: Tool automatically handles missing values (NaN)
        """
    )

# Support Section
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%); 
                border-radius: 12px;'>
        <h4>Need Help?</h4>
        <p>Check the documentation or contact the development team for support with pipeline tools.</p>
        <p style='color: #7f8c8d;'>📧 Support | 📚 Documentation | 💬 Feedback</p>
    </div>
    """,
    unsafe_allow_html=True,
)

