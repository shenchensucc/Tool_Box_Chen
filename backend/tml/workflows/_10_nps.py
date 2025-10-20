from ..data_processor import DataProcessor

def process_nps(source, loader_Assets, loader_TML, output_file):
    """Process NPS updates"""
    processor = DataProcessor()
    
    print("\nProcessing NPS...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_NPS"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_NPS = source_subset[
        (source_subset["CorrValue_NPS"].notna()) & 
        (source_subset["CorrValue_NPS"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_NPS.shape}")
    print(f"Unique values in CorrValue_NPS after filtering: {source_NPS['CorrValue_NPS'].unique()}")
    
    if not source_NPS.empty:
        print("Found records to process")
        
        # Map CorrValue_NPS directly to Piping Nominal Diameter - NPS in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_NPS,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_NPS": "Piping Nominal Diameter - NPS"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

