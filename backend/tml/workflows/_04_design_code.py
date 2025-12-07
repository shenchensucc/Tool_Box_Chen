from ..data_processor import DataProcessor

def process_design_code(source, loader_Assets, loader_TML, output_file):
    """Process Design Code updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Design Code...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Design_Code"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_DesignCode = source_subset[
        (source_subset["CorrValue_Design_Code"].notna()) & 
        (source_subset["CorrValue_Design_Code"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_DesignCode.shape}")
    
    if not source_DesignCode.empty:
        print(f"Found {len(source_DesignCode)} records to process")
        
        # Map CorrValue_Design_Code directly to Design Code in the column mapping
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_DesignCode,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Design_Code": "Design Code"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

