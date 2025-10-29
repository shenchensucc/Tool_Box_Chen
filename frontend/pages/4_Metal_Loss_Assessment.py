import sys
from pathlib import Path
from datetime import datetime, timedelta
import json
import io

import httpx
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Check if kaleido is available for image export
try:
    import kaleido
    KALEIDO_AVAILABLE = True
except ImportError:
    KALEIDO_AVAILABLE = False

# Alternative: Use plotly's built-in image export without kaleido
def export_plot_as_image(fig, format="png", width=1200, height=600):
    """Export plotly figure as image, trying multiple methods"""
    # Try default engine first (no kaleido requirement)
    try:
        return fig.to_image(format=format, width=width, height=height)
    except Exception as e1:
        # If default fails, try kaleido if available
        if KALEIDO_AVAILABLE:
            try:
                return fig.to_image(format=format, width=width, height=height, engine="kaleido")
            except Exception as e2:
                st.warning(f"Could not export chart as image (tried both engines): {str(e2)}")
                return None
        else:
            st.warning(f"Could not export chart as image: {str(e1)}")
            return None

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
set_page_config("Metal Loss Assessment", "🔬")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

# Header
display_header(
    "🔬 Metal Loss Assessment",
    "Assess metal loss features using modified B31G methodology",
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

# Preset scenarios dictionary
# User can modify this table with their own NPS configurations
PRESET_SCENARIOS = {
    "Customized": {
        "description": "Manually input all parameters",
        "do": 0.0,
        "tp": 0.0,
        "YS": 0.0,
        "TS": 0.0
    },
    "NPS 8 - Sch 40 - Grade X52": {
        "description": "NPS 8, Schedule 40, Grade X52",
        "do": 219.1,
        "tp": 8.18,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 8 - Sch 80 - Grade X52": {
        "description": "NPS 8, Schedule 80, Grade X52",
        "do": 219.1,
        "tp": 12.7,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 10 - Sch 40 - Grade X52": {
        "description": "NPS 10, Schedule 40, Grade X52",
        "do": 273.1,
        "tp": 9.27,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 10 - Sch 80 - Grade X52": {
        "description": "NPS 10, Schedule 80, Grade X52",
        "do": 273.1,
        "tp": 15.09,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 12 - Sch 40 - Grade X52": {
        "description": "NPS 12, Schedule 40, Grade X52",
        "do": 323.9,
        "tp": 10.31,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 12 - Sch 80 - Grade X52": {
        "description": "NPS 12, Schedule 80, Grade X52",
        "do": 323.9,
        "tp": 17.48,
        "YS": 359.0,
        "TS": 455.0
    },
    "NPS 10 - Sch 40 - Grade X60": {
        "description": "NPS 10, Schedule 40, Grade X60",
        "do": 273.1,
        "tp": 9.27,
        "YS": 414.0,
        "TS": 517.0
    },
}

# Information section
st.info("📋 **About This Tool**: Assess pipeline metal loss features over time using industry-standard modified B31G methodology.")

# Test Cases Section
with st.expander("🧪 Load R Package Test Cases", expanded=False):
    st.markdown("""
    **Quick Test**: Load parameters from R package test cases to verify Python implementation matches R results.
    
    These test cases are from the R package `mla` file `test-fmla.R`.
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("📊 Test Case 1: z > 50", use_container_width=True):
            st.session_state['test_case'] = 1
            st.session_state['scenario'] = 'Customized'
            st.rerun()
    
    with col2:
        if st.button("📊 Test Case 2: z ≤ 50", use_container_width=True):
            st.session_state['test_case'] = 2
            st.session_state['scenario'] = 'Customized'
            st.rerun()
    
    with col3:
        if st.button("📊 R Markdown Example", use_container_width=True):
            st.session_state['test_case'] = 3
            st.session_state['scenario'] = 'NPS 10 - Sch 40 - Grade X52'
            st.rerun()
    
    st.caption("After clicking a test case button, scroll down to review parameters and click 'Run Assessment'")

# Main content area
st.subheader("📝 Assessment Parameters")

# Check if test case was loaded
if 'test_case' in st.session_state and 'scenario' in st.session_state:
    default_scenario_idx = list(PRESET_SCENARIOS.keys()).index(st.session_state['scenario'])
else:
    default_scenario_idx = 0

# Preset scenario selection
scenario = st.selectbox(
    "Select Preset Scenario",
    options=list(PRESET_SCENARIOS.keys()),
    index=default_scenario_idx,
    help="Choose a preset configuration or 'Customized' to input all parameters manually"
)

selected_preset = PRESET_SCENARIOS[scenario]
st.caption(f"*{selected_preset['description']}*")

# Load test case parameters if selected
test_case_params = {}
if 'test_case' in st.session_state:
    test_case_num = st.session_state['test_case']
    
    if test_case_num == 1:
        # Test Case 1: z > 50
        test_case_params = {
            'do': 273.1,
            'tp': 5.16,
            'YS': 359.0,
            'TS': 455.0,
            'dimp_org_percent': 50.0,
            'Limp_org': 300.0,
            'feature_ID': 'Test-Case-1-z-greater-50',
            'vendor_ILI': 'Test Vendor',
            'ILI_dimp_tolerance': 0.0,
            'ILI_Limp_tolerance': 0.0,
            'CR_low': 0.0,
            'CR_ave': 0.0,
            'CR_high': 0.0,
            'month_CR': 1,
            'CR_Limp': 0.0
        }
        st.info("✅ **Test Case 1 Loaded**: z > 50 (Limp=300mm). This tests the linear Folias factor formula.")
        
    elif test_case_num == 2:
        # Test Case 2: z ≤ 50
        test_case_params = {
            'do': 273.1,
            'tp': 5.16,
            'YS': 359.0,
            'TS': 455.0,
            'dimp_org_percent': 50.0,
            'Limp_org': 200.0,
            'feature_ID': 'Test-Case-2-z-less-equal-50',
            'vendor_ILI': 'Test Vendor',
            'ILI_dimp_tolerance': 0.0,
            'ILI_Limp_tolerance': 0.0,
            'CR_low': 0.0,
            'CR_ave': 0.0,
            'CR_high': 0.0,
            'month_CR': 1,
            'CR_Limp': 0.0
        }
        st.info("✅ **Test Case 2 Loaded**: z ≤ 50 (Limp=200mm). This tests the polynomial Folias factor formula.")
        
    elif test_case_num == 3:
        # R Markdown Example
        test_case_params = {
            'do': 273.1,
            'tp': 6.35,
            'YS': 359.0,
            'TS': 455.0,
            'dimp_org_percent': 41.0,
            'Limp_org': 361.0,
            'feature_ID': '7',
            'vendor_ILI': 'ROSEN MFL-C',
            'ILI_dimp_tolerance': 15.0,
            'ILI_Limp_tolerance': 0.0,
            'CR_low': 0.196,
            'CR_ave': 0.245,
            'CR_high': 0.452,
            'month_CR': 48,
            'CR_Limp': 0.0
        }
        st.info("✅ **R Markdown Example Loaded**: Complete assessment scenario from PNG_Metal_Loss_Feature_Assessment.Rmd")
    
    # Clear the test case after loading
    if st.button("🔄 Clear Test Case and Reset", type="secondary"):
        del st.session_state['test_case']
        if 'scenario' in st.session_state:
            del st.session_state['scenario']
        st.rerun()

# Create tabs for organized input
tab1, tab2, tab3 = st.tabs(["🔧 Pipe & Material", "📏 Defect Information", "📈 Growth Rates & Assessment"])

with tab1:
    st.markdown("### Pipe Properties")
    col1, col2 = st.columns(2)
    
    with col1:
        is_customized = (scenario == "Customized")
        
        do = st.number_input(
            "Outside Diameter (mm)",
            min_value=0.0,
            value=float(test_case_params.get('do', selected_preset['do'])),
            step=0.1,
            disabled=not is_customized,
            help="Pipe outside diameter in millimeters"
        )
        
        tp = st.number_input(
            "Wall Thickness (mm)",
            min_value=0.0,
            value=float(test_case_params.get('tp', selected_preset['tp'])),
            step=0.01,
            disabled=not is_customized,
            help="Nominal wall thickness in millimeters"
        )
    
    with col2:
        YS = st.number_input(
            "Yield Strength (MPa)",
            min_value=0.0,
            value=float(test_case_params.get('YS', selected_preset['YS'])),
            step=1.0,
            disabled=not is_customized,
            help="Specified Minimum Yield Strength"
        )
        
        TS = st.number_input(
            "Tensile Strength (MPa)",
            min_value=0.0,
            value=float(test_case_params.get('TS', selected_preset['TS'])),
            step=1.0,
            disabled=not is_customized,
            help="Specified Minimum Tensile Strength"
        )

with tab2:
    st.markdown("### Defect Dimensions")
    col1, col2 = st.columns(2)
    
    with col1:
        dimp_org_percent = st.number_input(
            "Defect Depth (% of wall thickness)",
            min_value=0.0,
            max_value=100.0,
            value=float(test_case_params.get('dimp_org_percent', 41.0)),
            step=0.1,
            help="Depth of the defect as percentage of nominal wall thickness"
        )
        
        Limp_org = st.number_input(
            "Defect Length (mm)",
            min_value=0.0,
            value=float(test_case_params.get('Limp_org', 361.0)),
            step=1.0,
            help="Axial length of the defect"
        )
    
    with col2:
        feature_ID = st.text_input(
            "Feature ID",
            value=test_case_params.get('feature_ID', "Feature-001"),
            help="Unique identifier for this feature"
        )
    
    st.markdown("### ILI Information")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        vendor_ILI = st.text_input(
            "ILI Vendor",
            value=test_case_params.get('vendor_ILI', "ROSEN MFL-C"),
            help="In-Line Inspection vendor name"
        )
    
    with col2:
        date_ILI = st.date_input(
            "ILI Date",
            value=datetime.now() - timedelta(days=180),
            help="Date of the ILI run"
        )
    
    with col3:
        ILI_dimp_tolerance = st.number_input(
            "Depth Tolerance (%)",
            min_value=0.0,
            value=float(test_case_params.get('ILI_dimp_tolerance', 15.0)),
            step=0.1,
            help="ILI tool tolerance for depth measurement"
        )
        
        ILI_Limp_tolerance = st.number_input(
            "Length Tolerance (mm)",
            min_value=0.0,
            value=float(test_case_params.get('ILI_Limp_tolerance', 0.0)),
            step=1.0,
            help="ILI tool tolerance for length measurement"
        )

with tab3:
    st.markdown("### Corrosion Growth Rates")
    st.caption("Based on industry standards and historical ILI data correlation")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        CR_low = st.number_input(
            "Low Rate - 50th Percentile (mm/yr)",
            min_value=0.0,
            value=float(test_case_params.get('CR_low', 0.196)),
            step=0.001,
            format="%.3f",
            help="Conservative corrosion growth rate"
        )
    
    with col2:
        CR_ave = st.number_input(
            "Average Rate - 90th Percentile (mm/yr)",
            min_value=0.0,
            value=float(test_case_params.get('CR_ave', 0.245)),
            step=0.001,
            format="%.3f",
            help="Expected corrosion growth rate"
        )
    
    with col3:
        CR_high = st.number_input(
            "High Rate - 99th Percentile (mm/yr)",
            min_value=0.0,
            value=float(test_case_params.get('CR_high', 0.452)),
            step=0.001,
            format="%.3f",
            help="Worst-case corrosion growth rate"
        )
    
    st.markdown("### Assessment Period")
    col1, col2 = st.columns(2)
    
    with col1:
        month_CR = st.number_input(
            "Projection Period (months)",
            min_value=1,
            max_value=120,
            value=int(test_case_params.get('month_CR', 48)),
            step=1,
            help="Number of months to project forward"
        )
    
    with col2:
        CR_Limp = st.number_input(
            "Length Growth Rate (mm/yr)",
            min_value=0.0,
            value=float(test_case_params.get('CR_Limp', 0.0)),
            step=0.1,
            help="Defect length growth rate (typically 0)"
        )

# Process button
st.write("")  # Add spacing
process_button = st.button(
    "🚀 Run Assessment",
    type="primary",
    use_container_width=True
)

if process_button:
    # Validation
    if do <= 0 or tp <= 0:
        st.error("❌ Please provide valid pipe dimensions (diameter and thickness must be > 0)")
        st.stop()
    
    if YS <= 0 or TS <= 0:
        st.error("❌ Please provide valid material properties (YS and TS must be > 0)")
        st.stop()
    
    # Process the assessment
    with st.spinner("⏳ Calculating metal loss assessment... This may take a moment."):
        try:
            # Prepare the request
            data = {
                "do": do,
                "tp": tp,
                "YS": YS,
                "TS": TS,
                "dimp_org_percent": dimp_org_percent,
                "Limp_org": Limp_org,
                "date_ILI": date_ILI.strftime("%Y-%m-%d"),
                "ILI_dimp_tolerance": ILI_dimp_tolerance,
                "ILI_Limp_tolerance": ILI_Limp_tolerance,
                "CR_low": CR_low,
                "CR_ave": CR_ave,
                "CR_high": CR_high,
                "month_CR": month_CR,
                "feature_ID": feature_ID,
                "vendor_ILI": vendor_ILI,
                "CR_Limp": CR_Limp
            }
            
            # Call the API
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    "http://localhost:8000/api/pipeline/metal-loss/assess",
                    data=data,
                )
            
            if response.status_code == 200:
                results = response.json()
                
                st.success("✅ Assessment completed successfully!")
                
                # Display results
                st.markdown("---")
                st.header("📊 Assessment Results")
                
                # Input Parameters Summary Table
                with st.expander("📋 Input Parameters Summary", expanded=True):
                    inputs = results['inputs']
                    
                    params_data = {
                        "Parameter": [
                            "Feature Number/Identifier",
                            "Depth of the defect, %NWT",
                            "Length of the defect, mm",
                            "Outside diameter of the pipe, mm",
                            "Pipe wall thickness, mm",
                            "Yield strength of the material, MPa",
                            "Tensile strength of the material, MPa",
                            "ILI vendor",
                            "ILI time",
                            "ILI tool tolerance for depth, %",
                            "ILI tool tolerance for length, mm",
                            "Feature depth growth rate, mm/yr",
                            "Feature length growth rate, mm/yr"
                        ],
                        "Value": [
                            inputs['feature_ID'],
                            f"{inputs['dimp_org_percent']}",
                            f"{inputs['Limp_org']}",
                            f"{inputs['do']}",
                            f"{inputs['tp']}",
                            f"{inputs['YS']}",
                            f"{inputs['TS']}",
                            inputs['vendor_ILI'],
                            inputs['date_ILI'],
                            f"{inputs['ILI_dimp_tolerance']}",
                            f"{inputs['ILI_Limp_tolerance']}",
                            f"{inputs['CR_low']} (low), {inputs['CR_ave']} (avg), {inputs['CR_high']} (high)",
                            f"{inputs.get('CR_Limp', 0)}"
                        ]
                    }
                    
                    df_params = pd.DataFrame(params_data)
                    st.dataframe(df_params, use_container_width=True, hide_index=True)
                
                # Generate date sequence for x-axis
                date_start = datetime.strptime(inputs['date_ILI'], "%Y-%m-%d")
                date_seq = [date_start + timedelta(days=30*i) for i in range(month_CR)]
                
                # Depth Growth Chart
                st.markdown("### 📈 Predicted Defect Depth Growth")
                
                fig_depth = go.Figure()
                
                depth_low = results['depth_arrays']['low']
                depth_ave = results['depth_arrays']['ave']
                depth_high = results['depth_arrays']['high']
                
                fig_depth.add_trace(go.Scatter(
                    x=date_seq,
                    y=depth_low,
                    mode='lines',
                    name='Low Growth Rate',
                    line=dict(color='green', width=2)
                ))
                
                fig_depth.add_trace(go.Scatter(
                    x=date_seq,
                    y=depth_ave,
                    mode='lines',
                    name='Average Growth Rate',
                    line=dict(color='orange', width=2)
                ))
                
                fig_depth.add_trace(go.Scatter(
                    x=date_seq,
                    y=depth_high,
                    mode='lines',
                    name='High Growth Rate',
                    line=dict(color='red', width=2)
                ))
                
                # Add 80% wall thickness line
                wall_80 = results['calculated']['wall_thickness_80']
                fig_depth.add_hline(
                    y=wall_80,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="80% Wall Thickness",
                    annotation_position="right"
                )
                
                fig_depth.update_layout(
                    title="Predicted Defect Depth Growth",
                    xaxis_title="Date",
                    yaxis_title="Defect Depth (mm)",
                    hovermode='x unified',
                    legend=dict(x=0.02, y=0.98),
                    height=500
                )
                
                st.plotly_chart(fig_depth, use_container_width=True)
                
                # Depth Growth Table
                with st.expander("📋 Depth Growth Data Table"):
                    df_depth = pd.DataFrame({
                        'Month': list(range(month_CR)),
                        'Date': [d.strftime("%Y-%m-%d") for d in date_seq],
                        'Depth Low (mm)': [f"{d:.2f}" for d in depth_low],
                        'Depth Low (%)': [f"{d/tp*100:.2f}" for d in depth_low],
                        'Depth Ave (mm)': [f"{d:.2f}" for d in depth_ave],
                        'Depth Ave (%)': [f"{d/tp*100:.2f}" for d in depth_ave],
                        'Depth High (mm)': [f"{d:.2f}" for d in depth_high],
                        'Depth High (%)': [f"{d/tp*100:.2f}" for d in depth_high]
                    })
                    st.dataframe(df_depth, use_container_width=True, hide_index=True)
                
                # SOP Decay Chart
                st.markdown("### 📉 Predicted Safe Operating Pressure Decay")
                
                fig_sop = go.Figure()
                
                sop_low = results['sop_arrays']['low']
                sop_ave = results['sop_arrays']['ave']
                sop_high = results['sop_arrays']['high']
                
                fig_sop.add_trace(go.Scatter(
                    x=date_seq,
                    y=sop_low,
                    mode='lines',
                    name='Low Growth Rate',
                    line=dict(color='green', width=2)
                ))
                
                fig_sop.add_trace(go.Scatter(
                    x=date_seq,
                    y=sop_ave,
                    mode='lines',
                    name='Average Growth Rate',
                    line=dict(color='orange', width=2)
                ))
                
                fig_sop.add_trace(go.Scatter(
                    x=date_seq,
                    y=sop_high,
                    mode='lines',
                    name='High Growth Rate',
                    line=dict(color='red', width=2)
                ))
                
                # Add threshold line (example: 800 psi)
                fig_sop.add_hline(
                    y=800,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="800 psi Threshold",
                    annotation_position="right"
                )
                
                fig_sop.update_layout(
                    title="Predicted Safe Operating Pressure Decay",
                    xaxis_title="Date",
                    yaxis_title="Safe Operating Pressure (psi)",
                    hovermode='x unified',
                    legend=dict(x=0.02, y=0.98),
                    height=500
                )
                
                st.plotly_chart(fig_sop, use_container_width=True)
                
                # SOP Table
                with st.expander("📋 SOP Decay Data Table"):
                    df_sop = pd.DataFrame({
                        'Month': list(range(month_CR)),
                        'Date': [d.strftime("%Y-%m-%d") for d in date_seq],
                        'SOP Low (psi)': [f"{s:.2f}" for s in sop_low],
                        'SOP Ave (psi)': [f"{s:.2f}" for s in sop_ave],
                        'SOP High (psi)': [f"{s:.2f}" for s in sop_high]
                    })
                    st.dataframe(df_sop, use_container_width=True, hide_index=True)
                
                # SOP with Cutoff Chart
                st.markdown("### 📊 SOP Decay with 80% Wall Thickness Cutoff")
                
                cutoff_months = results['cutoff_months']
                
                fig_cutoff = go.Figure()
                
                # Truncate data at cutoff points
                cutoff_low_idx = min(cutoff_months['low'], month_CR)
                cutoff_ave_idx = min(cutoff_months['ave'], month_CR)
                cutoff_high_idx = min(cutoff_months['high'], month_CR)
                
                fig_cutoff.add_trace(go.Scatter(
                    x=date_seq[:cutoff_low_idx],
                    y=sop_low[:cutoff_low_idx],
                    mode='lines+markers',
                    name=f'Low (Cutoff: Month {cutoff_low_idx})',
                    line=dict(color='green', width=2),
                    marker=dict(size=6)
                ))
                
                fig_cutoff.add_trace(go.Scatter(
                    x=date_seq[:cutoff_ave_idx],
                    y=sop_ave[:cutoff_ave_idx],
                    mode='lines+markers',
                    name=f'Average (Cutoff: Month {cutoff_ave_idx})',
                    line=dict(color='orange', width=2),
                    marker=dict(size=6)
                ))
                
                fig_cutoff.add_trace(go.Scatter(
                    x=date_seq[:cutoff_high_idx],
                    y=sop_high[:cutoff_high_idx],
                    mode='lines+markers',
                    name=f'High (Cutoff: Month {cutoff_high_idx})',
                    line=dict(color='red', width=2),
                    marker=dict(size=6)
                ))
                
                fig_cutoff.add_hline(
                    y=800,
                    line_dash="dash",
                    line_color="red",
                    annotation_text="800 psi Threshold",
                    annotation_position="right"
                )
                
                fig_cutoff.update_layout(
                    title="SOP Decay (Up to 80% Wall Thickness)",
                    xaxis_title="Date",
                    yaxis_title="Safe Operating Pressure (psi)",
                    hovermode='x unified',
                    legend=dict(x=0.02, y=0.98),
                    height=500
                )
                
                st.plotly_chart(fig_cutoff, use_container_width=True)
                
                # Cutoff information
                with st.expander("ℹ️ 80% Wall Thickness Cutoff Information"):
                    st.write(f"**Low corrosion rate:** Reaches 80% wall thickness at Month {cutoff_months['low']}")
                    st.write(f"**Average corrosion rate:** Reaches 80% wall thickness at Month {cutoff_months['ave']}")
                    st.write(f"**High corrosion rate:** Reaches 80% wall thickness at Month {cutoff_months['high']}")
                
                # Store results and figures in session state for export and persistence
                st.session_state['metal_loss_results'] = results
                st.session_state['fig_depth'] = fig_depth
                st.session_state['fig_sop'] = fig_sop
                st.session_state['fig_cutoff'] = fig_cutoff
                st.session_state['feature_ID'] = feature_ID
                st.session_state['assessment_complete'] = True
                
            else:
                error_detail = response.json().get("detail", "Unknown error")
                st.error(f"❌ Error processing assessment: {error_detail}")
                
        except httpx.TimeoutException:
            st.error("❌ Request timed out. The calculation might be too complex.")
        except httpx.ConnectError:
            st.error("❌ Could not connect to the backend server. Please make sure it's running.")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")

# Export section - show if assessment is complete
if st.session_state.get('assessment_complete', False):
    st.markdown("---")
    st.subheader("📥 Export Report")
    
    st.info("💡 **Export to Word**: Download a comprehensive assessment report with all tables and charts.")
    
    # Retrieve stored data
    results = st.session_state['metal_loss_results']
    fig_depth = st.session_state['fig_depth']
    fig_sop = st.session_state['fig_sop']
    fig_cutoff = st.session_state['fig_cutoff']
    feature_ID = st.session_state['feature_ID']
    
    # Generate Word report button
    if st.button("📄 Generate Word Report", key="generate_word", type="primary", use_container_width=True):
        with st.spinner("⏳ Generating Word document..."):
            try:
                # Save Plotly charts as PNG images using our fallback function
                depth_img = export_plot_as_image(fig_depth, format="png", width=1200, height=600)
                sop_img = export_plot_as_image(fig_sop, format="png", width=1200, height=600)
                cutoff_img = export_plot_as_image(fig_cutoff, format="png", width=1200, height=600)
                
                # Check if any image export failed
                if not any([depth_img, sop_img, cutoff_img]):
                    st.warning("⚠️ Chart images could not be exported, but generating report without charts...")
                    # Set empty images for failed exports
                    depth_img = depth_img or b''
                    sop_img = sop_img or b''
                    cutoff_img = cutoff_img or b''
                
                # Prepare files for upload
                files = {
                    'depth_growth_chart': ('depth_growth.png', io.BytesIO(depth_img), 'image/png'),
                    'sop_decay_chart': ('sop_decay.png', io.BytesIO(sop_img), 'image/png'),
                    'sop_cutoff_chart': ('sop_cutoff.png', io.BytesIO(cutoff_img), 'image/png')
                }
                
                data_form = {
                    'assessment_results': json.dumps(results)
                }
                
                # Call export API
                with httpx.Client(timeout=120.0) as client:
                    export_response = client.post(
                        "http://localhost:8000/api/pipeline/metal-loss/export-word",
                        files=files,
                        data=data_form
                    )
                
                if export_response.status_code == 200:
                    # Store the document in session state for download
                    st.session_state['word_doc'] = export_response.content
                    st.session_state['doc_filename'] = f"Metal_Loss_Assessment_{feature_ID}_{datetime.now().strftime('%Y%m%d')}.docx"
                    st.success("✅ Word report generated successfully!")
                    st.rerun()  # Rerun to show download button
                else:
                    st.error(f"❌ Error generating report: {export_response.text}")
            
            except Exception as e:
                st.error(f"❌ Error exporting to Word: {str(e)}")
                if "kaleido" in str(e).lower():
                    st.info("💡 For better image export, install kaleido: `pip install kaleido`")
                else:
                    st.info("💡 Please try again or contact support if the issue persists.")
    
    # Show download button if document is ready
    if 'word_doc' in st.session_state:
        st.download_button(
            label="💾 Download Report (.docx)",
            data=st.session_state['word_doc'],
            file_name=st.session_state['doc_filename'],
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
            key="download_word"
        )
        st.caption("Click the button above to download your report")

# Help section
with st.expander("ℹ️ Help & Methodology"):
    st.markdown("""
    ### About Metal Loss Assessment
    
    This tool performs pipeline metal loss assessment using the **Modified B31G** methodology, 
    which is widely accepted in the pipeline integrity industry.
    
    ### Methodology
    
    **Modified B31G (ASME B31G-2009)**:
    - Calculates failure pressure based on defect geometry
    - Accounts for material properties and pipe dimensions
    - Uses Folias bulging factor for stress intensification
    - Default flow stress: SMYS + 69 MPa
    
    **Assessment Process**:
    1. Apply ILI tool tolerances to defect measurements
    2. Project defect growth using corrosion rates
    3. Calculate failure pressure at each time step
    4. Convert to Safe Operating Pressure (SOP = Pf / 1.25)
    5. Identify when defect reaches 80% wall thickness
    
    ### Corrosion Growth Rates
    
    Three scenarios are evaluated:
    - **Low (50th percentile)**: Conservative estimate
    - **Average (90th percentile)**: Expected growth rate
    - **High (99th percentile)**: Worst-case scenario
    
    Rates based on PRCI research and historical ILI correlation studies.
    
    ### Safety Factor
    
    - **Design Factor**: 1.25 (SOP = Failure Pressure / 1.25)
    - This provides margin for uncertainties in:
      - Material properties
      - Defect dimensions
      - Growth rate predictions
      - Measurement accuracy
    
    ### Limitations
    
    - Applicable for depth ≤ 80% wall thickness
    - Assumes uniform corrosion within defect
    - Does not account for multiple interacting defects
    - Longitudinal defects only (not circumferential)
    
    ### References
    
    - ASME B31G-2009: Manual for Determining the Remaining Strength of Corroded Pipelines
    - PRCI Report: Generic External Corrosion Growth Rate Distributions for Buried Pipelines
    - CSA Z662: Oil and Gas Pipeline Systems
    """)

# Footer
st.divider()
st.caption("Metal Loss Assessment Tool v1.0 | Chen's Engineer Toolbox")

