from ..data_processor import DataProcessor

def process_material_specification(source, loader_Assets, loader_TML, output_file):
    """Process Material Specification updates
    
    Returns:
        tuple: (records_count, output_file) if successful, (0, None) if no records
    """
    processor = DataProcessor()
    
    print("\nProcessing Material Specification...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Material"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_MaterialSpec = source_subset[
        (source_subset["CorrValue_Material"].notna()) & 
        (source_subset["CorrValue_Material"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_MaterialSpec.shape}")
    
    if not source_MaterialSpec.empty:
        print(f"Found {len(source_MaterialSpec)} records to process")
        
        # Map CorrValue_Material directly to Material Specification in the column mapping
        records_added = processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_MaterialSpec,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Material": "Material Specification"
            },
            output_file, "Assets", "TML"
        )
        return (records_added, output_file if records_added > 0 else None)
    else:
        print("No records found matching the criteria")
        return (0, None)

