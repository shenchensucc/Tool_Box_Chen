from ..data_processor import DataProcessor

def process_schedule(source, loader_Assets, loader_TML, output_file):
    """Process Schedule updates"""
    processor = DataProcessor()
    
    print("\nProcessing Schedule...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Schedule"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_Schedule = source_subset[
        (source_subset["CorrValue_Schedule"].notna()) & 
        (source_subset["CorrValue_Schedule"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_Schedule.shape}")
    print(f"Unique values in CorrValue_Schedule after filtering: {source_Schedule['CorrValue_Schedule'].unique()}")
    
    if not source_Schedule.empty:
        print("Found records to process")
        
        # Map CorrValue_Schedule directly to Schedule in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_Schedule,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Schedule": "Schedule"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

