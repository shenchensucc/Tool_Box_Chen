"""
Inspect Dig Package - Joint Summary and Feature Summary

Run with path to a dig package Excel file to see parsed values:
    python dev_tools/inspect_dig_package.py "path/to/dig_package.xlsx"

Or from project root with a relative path.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    if len(sys.argv) < 2:
        print("Usage: python dev_tools/inspect_dig_package.py <path_to_dig_package.xlsx>")
        print("Example: python dev_tools/inspect_dig_package.py 'C:/path/to/ID6012_DP_R0.xlsx'")
        return 1

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 1

    content = path.read_bytes()
    from backend.pipeline.dig_package_reader import parse_dig_package_excel, build_feature_map_from_dig_package

    feature_df, joint_df, metadata = parse_dig_package_excel(content)

    print("=" * 60)
    print("DIG PACKAGE INSPECTION")
    print("=" * 60)
    print(f"File: {path.name}")
    print(f"Feature section found: {metadata.get('feature_section_found')}")
    print(f"Joint section found: {metadata.get('joint_section_found')}")
    print()

    if joint_df is not None and not joint_df.empty:
        print("--- Joint Summary (raw) ---")
        print(f"Columns: {list(joint_df.columns)}")
        print(joint_df.to_string())
        print()

    # Build full feature map (target GWD longseam merged into feature_summary_raw)
    try:
        features, scatter_data, sources, col_map, _, feature_summary_raw = build_feature_map_from_dig_package(content)
        print("--- Target GWD longseam (from Joint Summary, merged into Feature Summary) ---")
        if feature_summary_raw:
            tgwd = feature_summary_raw.get("target_gwd")
            tlabel = feature_summary_raw.get("target_longseam_label")
            if tgwd is not None and tlabel:
                print(f"Target GWD {tgwd}: {tlabel}")
            else:
                print("(No target GWD longseam)")
        else:
            print("(No feature summary raw)")
        print()
        print("--- Seam welds (horizontal lines for figure) ---")
        for sw in scatter_data.get("seam_welds", []):
            print(sw)
        print()
        print(f"Total features: {len(features)}")
    except Exception as e:
        print(f"Error building feature map: {e}")
        import traceback
        traceback.print_exc()

    return 0


if __name__ == "__main__":
    sys.exit(main())
