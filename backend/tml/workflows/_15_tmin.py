from ..data_processor import DataProcessor

def process_tmin(source, loader_Assets, loader_TML, output_file):
    """Process Tmin (Minimum Thickness) updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Tmin (Minimum Thickness)...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Tmin"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_Tmin = source_subset[
        (source_subset["CorrValue_Tmin"].notna()) & 
        (source_subset["CorrValue_Tmin"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_Tmin.shape}")
    print(f"Unique values in CorrValue_Tmin after filtering: {source_Tmin['CorrValue_Tmin'].unique()}")
    
    if not source_Tmin.empty:
        print(f"Found {len(source_Tmin)} records to process")
        
        # Map CorrValue_Tmin directly to Minimum Thickness in the column mapping
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_Tmin,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Tmin": "Minimum Thickness"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

