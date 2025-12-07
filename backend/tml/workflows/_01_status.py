from ..data_processor import DataProcessor

def process_status_indicator(source, loader_Assets, loader_TML, output_file):
    """Process Status Indicator updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Status Indicator...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "AER_Status_CML"]
    source_subset = source[required_columns].copy()
    print(f"Source subset shape after selecting columns: {source_subset.shape}")
    
    # Filter records where AER_Status_CML contains 'To be de-active'
    source_Status = source_subset[source_subset["AER_Status_CML"].str.contains("To be de-active", na=False)].copy()
    print(f"Filtered data shape: {source_Status.shape}")
    
    if not source_Status.empty:
        print(f"Found {len(source_Status)} records to process")
        # Add Status Indicator column with 'Inactive' value
        source_Status.loc[:, "Status Indicator"] = "Inactive"
        
        # Drop the AER_Status_CML column before saving
        source_Status = source_Status.drop(columns=["AER_Status_CML"])
        
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_Status,
            {"CML Group ID": "TML Group ID", "sub-CML ID": "TML_ID", "Status Indicator": "Status Indicator"},
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

