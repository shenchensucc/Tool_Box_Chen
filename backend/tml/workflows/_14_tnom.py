from ..data_processor import DataProcessor

def process_tnom(source, loader_Assets, loader_TML, output_file):
    """Process Tnom (Nominal Thickness) updates"""
    processor = DataProcessor()
    
    print("\nProcessing Tnom (Nominal Thickness)...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Tnom"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_Tnom = source_subset[
        (source_subset["CorrValue_Tnom"].notna()) & 
        (source_subset["CorrValue_Tnom"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_Tnom.shape}")
    print(f"Unique values in CorrValue_Tnom after filtering: {source_Tnom['CorrValue_Tnom'].unique()}")
    
    if not source_Tnom.empty:
        print("Found records to process")
        
        # Map CorrValue_Tnom directly to TNominal Thickness in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_Tnom,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Tnom": "TNominal Thickness"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

