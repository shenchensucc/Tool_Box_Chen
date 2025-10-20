from ..data_processor import DataProcessor

def process_location_factor(source, loader_Assets, loader_TML, output_file):
    """Process Location Factor updates"""
    processor = DataProcessor()
    
    print("\nProcessing Location Factor...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_LocFactor"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_LF = source_subset[
        (source_subset["CorrValue_LocFactor"].notna()) & 
        (source_subset["CorrValue_LocFactor"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_LF.shape}")
    print(f"Unique values in CorrValue_LocFactor after filtering: {source_LF['CorrValue_LocFactor'].unique()}")
    
    if not source_LF.empty:
        print("Found records to process")
        
        # Map CorrValue_LocFactor directly to Location Factor in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_LF,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_LocFactor": "Location Factor"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

