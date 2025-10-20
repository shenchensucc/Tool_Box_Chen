from ..data_processor import DataProcessor

def process_temperature_coefficient(source, loader_Assets, loader_TML, output_file):
    """Process Temperature Coefficient updates"""
    processor = DataProcessor()
    
    print("\nProcessing Temperature Coefficient...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Temperature Coefficient"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only records where Temperature Coefficient is not 1
    source_TempCoef = source_subset[
        source_subset["Temperature Coefficient"] != 1
    ].copy()
    
    print(f"Filtered data shape: {source_TempCoef.shape}")
    print(f"Unique values in Temperature Coefficient after filtering: {source_TempCoef['Temperature Coefficient'].unique()}")
    
    if not source_TempCoef.empty:
        print("Found records to process")
        
        # Set all values to 1 in the filtered data
        source_TempCoef["Temperature Coefficient"] = 1
        
        # Map Temperature Coefficient to Temperature Factor in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_TempCoef,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Temperature Coefficient": "Temperature Factor"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

