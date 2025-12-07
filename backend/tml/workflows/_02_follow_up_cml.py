from ..data_processor import DataProcessor

def process_follow_up_cml(source, loader_Assets, loader_TML, output_file):
    """Process Follow Up CML updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Follow Up CML...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "AER_Status_CML"]
    source_subset = source[required_columns].copy()
    print(f"Source subset shape after selecting columns: {source_subset.shape}")
    
    # Filter records where AER_Status_CML contains 'Yes'
    source_FollowUp = source_subset[source_subset["AER_Status_CML"].str.contains("Yes", na=False)].copy()
    print(f"Filtered data shape: {source_FollowUp.shape}")
    
    if not source_FollowUp.empty:
        print(f"Found {len(source_FollowUp)} records to process")
        # Add Follow Up TML and TML Comment columns
        source_FollowUp.loc[:, "Follow Up TML"] = "True"
        source_FollowUp.loc[:, "TML Comment"] = "Follow up TML Flag - intended for AER section CML"
        
        # Drop the AER_Status_CML column before saving
        source_FollowUp = source_FollowUp.drop(columns=["AER_Status_CML"])
        
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_FollowUp,
            {
                "CML Group ID": "TML Group ID", 
                "sub-CML ID": "TML_ID", 
                "Follow Up TML": "Follow Up TML",
                "TML Comment": "TML Comment"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

