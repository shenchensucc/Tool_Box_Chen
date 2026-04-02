"""
ILI Excel ingestion: vendor-specific sheet/header detection and column mapping.

Shared by dig package generation, ILI Visual (`/api/ili/process-feature-map`), and CLI tools.
Low-level primitives live in :mod:`backend.pipeline.ili_reader`.

Dig Package ILI parsing can be time-limited via :func:`parse_ili_file_with_timeout` and env
``DIG_PACKAGE_ILI_PARSE_TIMEOUT_SEC`` (default 300 seconds; ``0`` = no limit).
"""

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Optional, Tuple

import pandas as pd

from backend.logging_config import get_logger
from backend.pipeline.ili_reader import (
    COLUMN_KEYWORDS as ILI_COLUMN_KEYWORDS,
    merge_keyword_sets,
    read_excel_with_detected_header,
)

logger = get_logger("backend.pipeline.ili_parse")

# Vendor ILI layouts (aligned with Dig Package Generator / frontend ``DIG_PACKAGE_ILI_FORMAT_OPTIONS``).
_ROSEN_BASE_KEYWORDS: Dict[str, list] = {
    "feature_id": ["ID#", "Feature Identifier", "Feature ID", "ILI Feature ID"],
    "feature_type": ["Feature Type", "Feature", "Event"],
    "feature_desc": ["Feature Description", "Description", "Anomaly"],
    "length": ["Length (mm)", "Length (in)", "Length"],
    "width": ["Width (mm)", "Width (in)", "Width"],
    "depth": ["Depth (%)", "Max Depth", "Peak Depth"],
    "orientation": ["Orientation (clock)", "Clock Orient.", "Orientation (hh:mm)"],
    "distance": ["Wheel Count (ft)", "Log Dist.", "ILI Chainage (m)", "Odometer (m)"],
    "joint_number": ["Joint No. or US GW No.", "Joint No", "US GW No"],
}

_BH_BASE_KEYWORDS: Dict[str, list] = {
    "feature_id": ["ANOM ID", "Anomaly ID", "ID", "Feature ID"],
    "feature_type": ["Anomaly Type", "Type", "Feature Type", "Classification"],
    "feature_desc": ["Description", "Anomaly Description", "Feature Description", "Comment"],
    "length": ["Axial Length", "Length (mm)", "Length"],
    "width": ["Circ Width", "Width (mm)", "Width"],
    "depth": ["Depth (%)", "Depth", "Max Depth"],
    "orientation": ["Clock Position", "Orientation", "O'Clock"],
    "distance": ["Log Distance", "Chainage", "Odometer", "Distance (m)"],
    "joint_number": ["Joint No", "US Joint No", "Weld Number"],
}

ILI_VENDOR_KEYWORD_OVERRIDES: Dict[str, Dict[str, list]] = {
    "TDW": {
        "feature_id": ["ID", "Feature Number", "FeatureID", "Target ID"],
        "feature_type": ["Type", "Feature Type", "Anomaly Type"],
        "feature_desc": ["Description", "Feature Description", "Anomaly Description"],
        "length": ["Length", "Length (in)", "Length (mm)"],
        "width": ["Width", "Width (in)", "Width (mm)"],
        "depth": ["Depth", "Depth (%)", "Max Depth"],
        "orientation": ["Orientation", "Clock Orientation", "O'Clock"],
        "distance": ["Chainage", "Odometer", "Distance"],
        "joint_number": ["Joint", "Joint Number", "Weld Number"],
    },
    "Rosen-MFLA": _ROSEN_BASE_KEYWORDS,
    "Rosen-MFLC": _ROSEN_BASE_KEYWORDS,
    "Rosen-EMAT": _ROSEN_BASE_KEYWORDS,
    "BH-EMAT": _BH_BASE_KEYWORDS,
    "BH-MFLA": _BH_BASE_KEYWORDS,
}

ILI_WORKSHEET_KEYWORDS = ["Pipetally", "Pipe Tally", "Tally", "True", "Page-1", "PNG ILI Pipeline Tally"]
ANOMALIES_WORKSHEET_KEYWORDS = ["Anomalies", "Anomaly", "Anomaly Listing"]


class ILIParseTimeoutError(RuntimeError):
    """Raised when :func:`parse_ili_file_with_timeout` exceeds its limit."""


def parse_ili_file_with_timeout(
    file_content: bytes,
    vendor_format: str = "Rosen-MFLA",
    *,
    timeout_sec: Optional[float] = None,
) -> Tuple[pd.DataFrame, Dict[str, Optional[str]], Optional[str]]:
    """
    Run :func:`parse_ili_file` in a worker thread and fail if it does not finish in time.

    Default timeout comes from env ``DIG_PACKAGE_ILI_PARSE_TIMEOUT_SEC`` (seconds); unset or invalid → 300.
    Use ``timeout_sec=0`` or a negative env value to disable (calls :func:`parse_ili_file` directly).
    """
    if timeout_sec is None:
        raw = os.environ.get("DIG_PACKAGE_ILI_PARSE_TIMEOUT_SEC", "300").strip()
        try:
            timeout_sec = float(raw)
        except ValueError:
            timeout_sec = 300.0
    if timeout_sec <= 0:
        return parse_ili_file(file_content, vendor_format)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(parse_ili_file, file_content, vendor_format)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeoutError as e:
            raise ILIParseTimeoutError(
                f"ILI parse timed out after {timeout_sec:.0f}s ({vendor_format!r}). "
                "Reduce workbook size, split sheets, or set DIG_PACKAGE_ILI_PARSE_TIMEOUT_SEC "
                "(seconds; 0 = no limit)."
            ) from e


def parse_ili_file(
    file_content: bytes,
    vendor_format: str = "Rosen-MFLA",
) -> Tuple[pd.DataFrame, Dict[str, Optional[str]], Optional[str]]:
    """
    Parse ILI (In-Line Inspection) Excel using vendor-specific sheet selection and column mapping.

    Returns:
        DataFrame, column mapping (standard key → sheet column name), detected worksheet name.
    """
    sheet_keywords = ANOMALIES_WORKSHEET_KEYWORDS if "Rosen" in vendor_format else ILI_WORKSHEET_KEYWORDS
    keyword_map = merge_keyword_sets(
        ILI_COLUMN_KEYWORDS,
        ILI_VENDOR_KEYWORD_OVERRIDES.get(vendor_format, ILI_VENDOR_KEYWORD_OVERRIDES["Rosen-MFLA"]),
    )
    df, column_mapping, sheet_name, header_row = read_excel_with_detected_header(
        file_content=file_content,
        keyword_map=keyword_map,
        sheet_keywords=sheet_keywords,
        min_matches=4,
    )
    logger.info(
        "parse_ili_file: vendor=%s, sheet=%r, header_row=%s, mapped=%s",
        vendor_format,
        sheet_name,
        header_row,
        list(column_mapping.keys()),
    )
    return df, column_mapping, sheet_name
