from ..data_processor import DataProcessor

def process_piping_formula(source, loader_Assets, loader_TML, output_file):
    """Process Piping Formula updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Piping Formula...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Piping Formula"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep not "E" values
    source_PipingFormula = source_subset[
        (source_subset["Piping Formula"] != "E")
    ].copy()
    
    print(f"Filtered data shape: {source_PipingFormula.shape}")
    print(f"Unique values in Piping Formula after filtering: {source_PipingFormula['Piping Formula'].unique()}")
    
    if not source_PipingFormula.empty:
        print(f"Found {len(source_PipingFormula)} records to process")
        
        # Set all values to "E" in the filtered data
        source_PipingFormula["Piping Formula"] = "E"
        
        # Map Piping Formula to the output column
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_PipingFormula,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Piping Formula": "Piping Formula"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

