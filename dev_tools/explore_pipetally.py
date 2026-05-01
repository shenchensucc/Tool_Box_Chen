"""Explore the Pipe Tally sheet structure of the test ILI file."""
import pandas as pd
import openpyxl

PATH = (
    r"c:\Users\cshen\trisummit\PNG - Asset Integrity - Documents"
    r"\General\003_TIMP\003_West_ML\000_Common\IDP\2026_Planning"
    r"\00_ILI_including_2025_repair\R4 to TPLS (209-240)\Test 209-240.xlsx"
)
SHEET = "Pipe Tally"

# --- Raw read (no header detection) so we see everything ---
df_raw = pd.read_excel(PATH, sheet_name=SHEET, header=None)
print(f"Shape (raw): {df_raw.shape}")
print()

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 300)
pd.set_option("display.max_colwidth", 60)

print("=== First 40 rows (raw) ===")
print(df_raw.head(40).to_string())
print()

# --- Find the header row: first row where >4 cells are non-null strings ---
header_row = None
for i, row in df_raw.iterrows():
    non_null = row.dropna()
    if len(non_null) >= 4:
        header_row = i
        print(f"Candidate header at row index {i}: {non_null.tolist()[:10]}")
        break

if header_row is not None:
    df = pd.read_excel(PATH, sheet_name=SHEET, header=header_row)
    print(f"\n=== With header at row {header_row} ===")
    print("Columns:", df.columns.tolist())
    print()
    print("First 20 data rows:")
    print(df.head(20).to_string())
