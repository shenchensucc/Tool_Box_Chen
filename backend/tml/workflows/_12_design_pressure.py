from ..data_processor import DataProcessor

def process_design_pressure(source, loader_Assets, loader_TML, output_file):
    """Process Design Pressure updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Design Pressure...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_P"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_DesignPressure = source_subset[
        (source_subset["CorrValue_P"].notna()) & 
        (source_subset["CorrValue_P"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_DesignPressure.shape}")
    print(f"Unique values in CorrValue_P after filtering: {source_DesignPressure['CorrValue_P'].unique()}")
    
    if not source_DesignPressure.empty:
        print(f"Found {len(source_DesignPressure)} records to process")
        # Round CorrValue_P to integer (no decimals)
        source_DesignPressure["CorrValue_P"] = source_DesignPressure["CorrValue_P"].round(0).astype(int)
        # Map CorrValue_P directly to Design Pressure in the column mapping
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_DesignPressure,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_P": "Design Pressure"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

