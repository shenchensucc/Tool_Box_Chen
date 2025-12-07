from ..data_processor import DataProcessor

def process_code_year_tmin(source, loader_Assets, loader_TML, output_file):
    """Process Code Year T-Min Formula updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    print("\nProcessing Code Year T-Min Formula...")
    print(f"Source data shape before filtering: {source.shape}")
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Code Year (T-Min Formula)"]
    source_subset = source[required_columns].copy()
    source_CodeYear = source_subset[
        source_subset["Code Year (T-Min Formula)"] != "N/A"
    ].copy()
    print(f"Filtered data shape: {source_CodeYear.shape}")
    if not source_CodeYear.empty:
        print(f"Found {len(source_CodeYear)} records to process")
        source_CodeYear["Code Year (T-Min Formula)"] = "N/A"
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_CodeYear,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Code Year (T-Min Formula)": "Code Year (T-Min Formula)"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

