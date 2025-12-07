from ..data_processor import DataProcessor

def process_od(source, loader_Assets, loader_TML, output_file):
    """Process Outside Diameter (OD) updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
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
    
    if not source_OD.empty:
        print(f"Found {len(source_OD)} records to process")
        
        # Map CorrValue_OD directly to Outside Diameter in the column mapping
        records_added = processor.append_and_save(
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
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

