from ..data_processor import DataProcessor

def process_override_allowable_stress(source, loader_Assets, loader_TML, output_file):
    """Process Override Allowable Stress updates"""
    processor = DataProcessor()
    print("\nProcessing Override Allowable Stress...")
    print(f"Source data shape before filtering: {source.shape}")
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Override Allowable Stress"]
    source_subset = source[required_columns].copy()
    source_OAS = source_subset[
        (source_subset["Override Allowable Stress"] != "True") & (source_subset["Override Allowable Stress"] != True)
    ].copy()
    print(f"Filtered data shape: {source_OAS.shape}")
    print(f"Unique values in Override Allowable Stress after filtering: {source_OAS['Override Allowable Stress'].unique()}")
    if not source_OAS.empty:
        print("Found records to process")
        source_OAS["Override Allowable Stress"] = "True"
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_OAS,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Override Allowable Stress": "Override Allowable Stress"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

