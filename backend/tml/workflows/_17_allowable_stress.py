from ..data_processor import DataProcessor

def process_allowable_stress(source, loader_Assets, loader_TML, output_file):
    """Process Allowable Stress updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    print("\nProcessing Allowable Stress...")
    print(f"Source data shape before filtering: {source.shape}")
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "AER_SMYS"]
    source_subset = source[required_columns].copy()
    
    # Process filtered records (non-zero and non-NA)
    source_AS = source_subset[
        (source_subset["AER_SMYS"].notna()) & (source_subset["AER_SMYS"] != 0)
    ].copy()
    print(f"Filtered data shape: {source_AS.shape}")
    
    records_added = 0
    
    if not source_AS.empty:
        print(f"Found {len(source_AS)} records to process for filtered output")
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_AS,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "AER_SMYS": "Allowable Stress"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the filter criteria")
    
    # Process all records
    print("\nProcessing all Allowable Stress records...")
    if not source_subset.empty:
        print(f"Found {len(source_subset)} records to process for all records output")
        # Get the all records output file path from the same directory
        all_output_file = output_file.replace("AllowableStress.xlsx", "AllowableStress_All.xlsx")
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_subset,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "AER_SMYS": "Allowable Stress"
            },
            all_output_file, "Assets", "TML"
        )
    else:
        print("No records found for all records output")
    
    # Return count from filtered records (main output)
    return (records_added, output_file if records_added > 0 else None)

