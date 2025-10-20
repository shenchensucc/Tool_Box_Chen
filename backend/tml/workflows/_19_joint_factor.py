from ..data_processor import DataProcessor

def process_joint_factor(source, loader_Assets, loader_TML, output_file):
    """Process Joint Factor updates"""
    processor = DataProcessor()
    print("\nProcessing Joint Factor...")
    print(f"Source data shape before filtering: {source.shape}")
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Joint Factor"]
    source_subset = source[required_columns].copy()
    source_JF = source_subset[
        source_subset["Joint Factor"] != 1
    ].copy()
    print(f"Filtered data shape: {source_JF.shape}")
    print(f"Unique values in Joint Factor after filtering: {source_JF['Joint Factor'].unique()}")
    if not source_JF.empty:
        print("Found records to process")
        source_JF["Joint Factor"] = 1
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_JF,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Joint Factor": "Joint Factor"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

