from ..data_processor import DataProcessor

def process_od(source, loader_Assets, loader_TML, output_file):
    """Process Outside Diameter (OD) updates"""
    processor = DataProcessor()
    
    print("\nProcessing Outside Diameter (OD)...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_OD"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_OD = source_subset[
        (source_subset["CorrValue_OD"].notna()) & 
        (source_subset["CorrValue_OD"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_OD.shape}")
    print(f"Unique values in CorrValue_OD after filtering: {source_OD['CorrValue_OD'].unique()}")
    
    if not source_OD.empty:
        print("Found records to process")
        
        # Map CorrValue_OD directly to Outside Diameter in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_OD,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_OD": "Outside Diameter"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

