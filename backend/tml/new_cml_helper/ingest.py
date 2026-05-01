"""Load uploaded bytes into pandas structures."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Tuple

import pandas as pd


def ingest_files(uploads: List[Tuple[str, bytes]]) -> Dict[str, Dict[str, Any]]:
    """Parse uploads into {filename: {type, sheets: {sheet_name: DataFrame}}}."""
    result: Dict[str, Dict[str, Any]] = {}
    for filename, content in uploads:
        name_lower = filename.lower()
        try:
            if name_lower.endswith(".csv"):
                df = pd.read_csv(io.BytesIO(content), dtype=str, encoding_errors="replace")
                result[filename] = {"type": "csv", "sheets": {"CSV": df}}
            elif name_lower.endswith(".xlsx") or name_lower.endswith(".xls"):
                xl = pd.ExcelFile(io.BytesIO(content))
                sheets = {}
                for sn in xl.sheet_names:
                    sheets[sn] = pd.read_excel(xl, sheet_name=sn, dtype=str)
                result[filename] = {"type": "excel", "sheets": sheets}
            else:
                result[filename] = {"type": "unsupported", "sheets": {}, "error": "Only .csv, .xlsx, .xls supported"}
        except Exception as e:
            result[filename] = {"type": "error", "sheets": {}, "error": str(e)}
    return result

