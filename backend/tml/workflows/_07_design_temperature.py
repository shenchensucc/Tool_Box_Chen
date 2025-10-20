from ..data_processor import DataProcessor

def process_design_temperature(source, loader_Assets, loader_TML, output_file):
    """Process Design Temperature updates"""
    processor = DataProcessor()
    
    print("\nProcessing Design Temperature...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_T"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_DesignTemp = source_subset[
        (source_subset["CorrValue_T"].notna()) & 
        (source_subset["CorrValue_T"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_DesignTemp.shape}")
    print(f"Unique values in CorrValue_T after filtering: {source_DesignTemp['CorrValue_T'].unique()}")
    
    if not source_DesignTemp.empty:
        print("Found records to process")
        
        # Map CorrValue_T directly to Design Temperature in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_DesignTemp,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_T": "Design Temperature"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

