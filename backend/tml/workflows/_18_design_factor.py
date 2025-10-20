from ..data_processor import DataProcessor

def process_design_factor(source, loader_Assets, loader_TML, output_file):
    """Process Design Factor updates"""
    processor = DataProcessor()
    print("\nProcessing Design Factor...")
    print(f"Source data shape before filtering: {source.shape}")
    required_columns = ["Equipment ID", "CML Group ID", "sub-CML ID", "Design Factor"]
    source_subset = source[required_columns].copy()
    source_DF = source_subset[
        source_subset["Design Factor"] != 0.8
    ].copy()
    print(f"Filtered data shape: {source_DF.shape}")
    print(f"Unique values in Design Factor after filtering: {source_DF['Design Factor'].unique()}")
    if not source_DF.empty:
        print("Found records to process")
        source_DF["Design Factor"] = 0.8
        processor.append_and_save(
            loader_Assets,
            loader_TML,
            source_DF,
            {
                "CML Group ID": "TML Group ID",
                "sub-CML ID": "TML_ID",
                "Design Factor": "Design Factor"
            },
            output_file, "Assets", "TML"
        )
    else:
        print("No records found matching the criteria")

