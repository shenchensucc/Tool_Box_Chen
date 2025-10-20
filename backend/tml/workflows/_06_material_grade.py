from ..data_processor import DataProcessor

def process_material_grade(source, loader_Assets, loader_TML, output_file):
    """Process Material Grade updates"""
    processor = DataProcessor()
    
    print("\nProcessing Material Grade...")
    print(f"Source data shape before filtering: {source.shape}")
    
    # Select required columns
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "CorrValue_Grade"]
    source_subset = source[required_columns].copy()
    
    # Filter records: keep only non-empty AND non-zero values
    source_MaterialGrade = source_subset[
        (source_subset["CorrValue_Grade"].notna()) & 
        (source_subset["CorrValue_Grade"] != 0)
    ].copy()
    
    print(f"Filtered data shape: {source_MaterialGrade.shape}")
    print(f"Unique values in CorrValue_Grade after filtering: {source_MaterialGrade['CorrValue_Grade'].unique()}")
    
    if not source_MaterialGrade.empty:
        print("Found records to process")
        
        # Map CorrValue_Grade directly to Material Grade in the column mapping
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_MaterialGrade,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "CorrValue_Grade": "Material Grade"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

