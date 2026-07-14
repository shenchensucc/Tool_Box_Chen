"""
Metal Loss Assessment Calculations based on Modified B31G methodology.
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from backend.pipeline.ili_reader import identify_ili_columns
from backend.logging_config import get_logger

logger = get_logger("backend.pipeline.metal_loss")


def calculate_folias_factor(
    do: float,
    tp: float,
    Limp: float,
    method: str = "mb31g",
    z: Optional[float] = None
) -> Union[float, np.ndarray]:
    """
    Calculate Folias/bulging factor for metal loss assessment.
    
    Parameters:
    -----------
    do : float
        Outside diameter of pipe (mm)
    tp : float
        Wall thickness of pipe (mm)
    Limp : float
        Length of the imperfection (mm)
    method : str
        Failure stress equation method. Options:
        'b31g', 'mb31g', 'ng18', 'rstreng', 'lpc1', 'shell92'
    z : float, optional
        Normalized parameter. If None, calculated as L²/(do × tp)
    
    Returns:
    --------
    float or ndarray
        Folias/bulging factor
    
    Examples:
    ---------
    >>> calculate_folias_factor(do=273.1, tp=5.16, Limp=100, method="mb31g")
    """
    # Calculate normalized parameter if not provided
    if z is None:
        z = Limp ** 2 / (do * tp)
    
    # Handle array inputs
    is_array = isinstance(z, np.ndarray)
    if not is_array:
        z = np.array([z])
    
    Mfolias = np.full_like(z, np.nan, dtype=float)
    
    if method == "b31g":
        # B31G: Only valid for z <= 20
        valid_idx = z <= 20
        Mfolias[valid_idx] = (1 + 0.80 * z[valid_idx]) ** 0.5
        # For z > 20, Mfolias remains NaN
        
    elif method == "ng18":
        # NG-18 method
        Mfolias = (1 + 0.6275 * z - 0.003375 * z ** 2) ** 0.5
        
    elif method in ["mb31g", "rstreng"]:
        # Modified B31G or RSTRENG
        valid_idx = z <= 50
        Mfolias[valid_idx] = (1 + 0.6275 * z[valid_idx] - 0.003375 * z[valid_idx] ** 2) ** 0.5
        Mfolias[~valid_idx] = 0.032 * z[~valid_idx] + 3.3
        
    elif method == "lpc1":
        # LPC-1 method
        Mfolias = (1 + 0.31 * z) ** 0.5
        
    elif method == "shell92":
        # Shell 92 method
        Mfolias = (1 + 0.8 * z) ** 0.5
        
    else:
        raise ValueError(f"Invalid method: {method}. Choose from: b31g, mb31g, ng18, rstreng, lpc1, shell92")
    
    return Mfolias[0] if not is_array else Mfolias


def calculate_failure_pressure(
    dimp: Union[float, List[float], np.ndarray],
    Limp: Union[float, np.ndarray],
    do: float,
    tp: float,
    YS: float,
    TS: float,
    method: Optional[str] = None,
    Sflow: Optional[float] = None,
    Ai_Aoi: Optional[float] = None
) -> Dict[str, Union[np.ndarray, Dict]]:
    """
    Calculate failure stress and pressure for metal loss evaluation.
    
    Parameters:
    -----------
    dimp : float, list, or ndarray
        Depth of the defect (mm)
    Limp : float or ndarray
        Length of the defect (mm). Can be a scalar or an array matching dimp length.
    do : float
        Outside diameter of pipe (mm)
    tp : float
        Wall thickness of pipe (mm)
    YS : float
        Yield strength of material (MPa)
    TS : float
        Tensile strength of material (MPa)
    method : str, optional
        Method: 'b31g', 'mb31g', 'ng18', 'rstreng', 'lpc1', 'shell92'
        If None, defaults to 'mb31g'
    Sflow : float, optional
        User-defined flow stress (MPa). If None, calculated based on method
    Ai_Aoi : float, optional
        For rstreng: ratio of corroded area to original area
    
    Returns:
    --------
    dict
        Dictionary with keys:
        - 'inp': Input parameters
        - 'ans': Results with 'Sfail' (failure stress, kPa) and 'Pf' (failure pressure, kPa)
    
    Examples:
    ---------
    >>> result = calculate_failure_pressure(
    ...     dimp=2.58, Limp=300, do=273.1, tp=5.16, YS=359, TS=455
    ... )
    >>> print(result['ans']['Pf'])
    """
    # Convert inputs to numpy arrays
    dimp = np.atleast_1d(dimp)
    n = len(dimp)
    
    # Set default method and flow stress
    if method is None and Sflow is None:
        method = "mb31g"
        Sflow = YS + 69
    elif method is not None and Sflow is None:
        raise ValueError("Must supply Sflow when method is supplied, e.g., 1.10 * SMYS")
    
    # Calculate normalized depth
    d_t = dimp / tp
    
    # Check applicability range
    warnings = []
    if np.any(d_t > 0.80):
        warnings.append("some d_t ratio > 80% detected")
    
    # Calculate Folias factor (vectorized)
    Mfolias_values = calculate_folias_factor(do, tp, Limp, method)
    
    # Initialize remaining strength factor
    Rs = np.full(n, np.nan)
    
    # Calculate remaining strength based on method
    if method == "b31g":
        # For z <= 20
        valid_idx = ~np.isnan(Mfolias_values)
        if isinstance(Mfolias_values, np.ndarray):
            Rs[valid_idx] = (1 - (2/3) * d_t[valid_idx]) / (1 - (2/3) * d_t[valid_idx] / Mfolias_values[valid_idx])
            # For z > 20
            invalid_idx = np.isnan(Mfolias_values)
            Rs[invalid_idx] = 1 - d_t[invalid_idx]
        else:
            if not np.isnan(Mfolias_values):
                Rs = (1 - (2/3) * d_t) / (1 - (2/3) * d_t / Mfolias_values)
            else:
                Rs = 1 - d_t
        
    elif method == "mb31g":
        Rs = (1 - 0.85 * d_t) / (1 - 0.85 * d_t / Mfolias_values)
        
    elif method == "ng18":
        Rs = (1 - d_t) / (1 - d_t / Mfolias_values)
        
    elif method == "rstreng":
        if Ai_Aoi is None:
            raise ValueError("Ai_Aoi required for rstreng method")
        Rs = (1 - Ai_Aoi) / (1 - Ai_Aoi / Mfolias_values)
        
    elif method == "lpc1":
        Rs = (1 - d_t) / (1 - d_t / Mfolias_values)
        
    elif method == "shell92":
        Rs = (1 - d_t) / (1 - d_t / Mfolias_values)
    
    # Calculate failure stress (convert MPa to kPa)
    Sfail = Sflow * Rs * 1000
    
    # Calculate failure pressure for defect-free pipe
    Po = 2 * Sflow / (do / tp)
    
    # Calculate failure pressure (kPa)
    Pf = Po * Rs * 1000
    
    # Prepare input parameters
    inp = {
        'do': do,
        'tp': tp,
        'YS': YS,
        'TS': TS,
        'dimp': dimp,
        'Limp': Limp,
        'Sflow': Sflow,
        'method': method
    }
    
    # Prepare results
    ans = {
        'Sfail': Sfail,
        'Pf': Pf
    }
    
    return {
        'inp': inp,
        'ans': ans,
        'warnings': warnings
    }


def assess_metal_loss_feature(
    do: float,
    tp: float,
    YS: float,
    TS: float,
    dimp_org_percent: float,
    Limp_org: float,
    date_ILI: str,
    ILI_dimp_tolerance: float,
    ILI_Limp_tolerance: float,
    CR_low: float,
    CR_ave: float,
    CR_high: float,
    month_CR: int,
    feature_ID: str = "",
    vendor_ILI: str = "",
    CR_Limp: float = 0.0
) -> Dict:
    """
    Complete metal loss feature assessment over time.
    
    Parameters:
    -----------
    do : float
        Outside diameter of pipe (mm)
    tp : float
        Uncorroded pipe wall thickness (mm)
    YS : float
        Specified Minimum Yield Strength (MPa)
    TS : float
        Specified Minimum Tensile Strength (MPa)
    dimp_org_percent : float
        Depth of defect as % of nominal wall thickness
    Limp_org : float
        Length of defect (mm)
    date_ILI : str
        Date of ILI run (YYYY-MM-DD)
    ILI_dimp_tolerance : float
        ILI tool tolerance for depth (%)
    ILI_Limp_tolerance : float
        ILI tool tolerance for length (mm)
    CR_low : float
        Low corrosion rate (mm/yr)
    CR_ave : float
        Average corrosion rate (mm/yr)
    CR_high : float
        High corrosion rate (mm/yr)
    month_CR : int
        Number of months to project
    feature_ID : str, optional
        Feature identifier
    vendor_ILI : str, optional
        ILI vendor name
    CR_Limp : float, optional
        Length growth rate (mm/yr)
    
    Returns:
    --------
    dict
        Complete assessment results including depth arrays, pressure arrays, dates, etc.
    """
    # Calculate actual defect dimensions with tolerances
    dimp = (dimp_org_percent + ILI_dimp_tolerance) * 0.01 * tp
    Limp = Limp_org + ILI_Limp_tolerance
    
    # Calculate depth growth arrays (monthly increments)
    dimp_low = np.arange(month_CR) * (CR_low / 12) + dimp
    dimp_ave = np.arange(month_CR) * (CR_ave / 12) + dimp
    dimp_high = np.arange(month_CR) * (CR_high / 12) + dimp
    
    # Calculate failure pressures
    fp_low = calculate_failure_pressure(dimp_low, Limp, do, tp, YS, TS)
    fp_ave = calculate_failure_pressure(dimp_ave, Limp, do, tp, YS, TS)
    fp_high = calculate_failure_pressure(dimp_high, Limp, do, tp, YS, TS)
    
    # Convert to Safe Operating Pressure (SOP) in psi with safety factor
    # kPa to psi conversion: 0.14503774, safety factor: 0.8
    fp_low_SOP = fp_low['ans']['Pf'] * 0.14503774 * 0.8
    fp_ave_SOP = fp_ave['ans']['Pf'] * 0.14503774 * 0.8
    fp_high_SOP = fp_high['ans']['Pf'] * 0.14503774 * 0.8
    
    # Calculate 80% wall thickness cutoff
    wall_thickness_80 = tp * 0.8
    
    # Find cutoff months where depth reaches 80% wall thickness
    cutoff_low = np.where(dimp_low >= wall_thickness_80)[0]
    cutoff_ave = np.where(dimp_ave >= wall_thickness_80)[0]
    cutoff_high = np.where(dimp_high >= wall_thickness_80)[0]
    
    # Return -1 to indicate "safe" (no cutoff found within period)
    # This avoids ambiguity where "month_CR" could mean it failed exactly at the last month
    safe_indicator = -1
    
    cutoff_month_low = cutoff_low[0] if len(cutoff_low) > 0 else safe_indicator
    cutoff_month_ave = cutoff_ave[0] if len(cutoff_ave) > 0 else safe_indicator
    cutoff_month_high = cutoff_high[0] if len(cutoff_high) > 0 else safe_indicator
    
    return {
        'inputs': {
            'feature_ID': feature_ID,
            'vendor_ILI': vendor_ILI,
            'date_ILI': date_ILI,
            'do': do,
            'tp': tp,
            'YS': YS,
            'TS': TS,
            'dimp_org_percent': dimp_org_percent,
            'Limp_org': Limp_org,
            'ILI_dimp_tolerance': ILI_dimp_tolerance,
            'ILI_Limp_tolerance': ILI_Limp_tolerance,
            'CR_low': CR_low,
            'CR_ave': CR_ave,
            'CR_high': CR_high,
            'CR_Limp': CR_Limp,
            'month_CR': month_CR
        },
        'calculated': {
            'dimp': dimp,
            'Limp': Limp,
            'wall_thickness_80': wall_thickness_80
        },
        'depth_arrays': {
            'low': dimp_low.tolist(),
            'ave': dimp_ave.tolist(),
            'high': dimp_high.tolist()
        },
        'sop_arrays': {
            'low': fp_low_SOP.tolist(),
            'ave': fp_ave_SOP.tolist(),
            'high': fp_high_SOP.tolist()
        },
        'cutoff_months': {
            'low': int(cutoff_month_low),
            'ave': int(cutoff_month_ave),
            'high': int(cutoff_month_high)
        }
    }


# find_column_names has been moved to backend.pipeline.ili_reader


def mass_assess_metal_loss(
    df: pd.DataFrame,
    do: float,
    tp: float,
    YS: float,
    TS: float,
    depth_tolerance: float,
    length_tolerance: float,
    depth_cr: float,
    length_cr: float,
    start_year: int,
    ili_date: Optional[str] = None,
    maop_psi: Optional[float] = None,
    safety_factor: float = 1.25,
    depth_cr_low: Optional[float] = None,
    depth_cr_mid: Optional[float] = None,
    depth_cr_high: Optional[float] = None,
    return_summary: bool = False,
):
    """
    Perform mass assessment for metal loss features over 11 years (start_year through
    start_year+10 inclusive), producing output columns that match the IDP planning format.

    For each feature the function computes:
    - ``Date to Become a Defect`` – calendar date when depth (with tolerance) reaches 80 % WT
    - ``Years to Become a Defect`` – corresponding duration from the ILI date
    - ``Failure Mode`` – always "Leak" for metal loss
    - ``Active/Inactive`` – "Active" for all growing features
    - One Pf (psi) column per year labelled with the integer year (e.g. 2025, 2026, …)

    Parameters
    ----------
    df : pd.DataFrame
        Input data with metal loss features.
    do : float
        Outside diameter (mm).
    tp : float
        Wall thickness (mm).
    YS : float
        Yield strength (MPa).
    TS : float
        Tensile strength (MPa).
    depth_tolerance : float
        ILI depth measurement tolerance (% WT).
    length_tolerance : float
        ILI length measurement tolerance (mm).
    depth_cr : float
        Depth corrosion rate (mm/year).
    length_cr : float
        Length growth rate (mm/year).
    start_year : int
        Calendar year of the ILI run.  Used as year-0 for Pf columns and,
        together with ``ili_date``, as the reference date for defect-date maths.
    ili_date : str, optional
        ISO date string of the ILI run (``YYYY-MM-DD``).  Defaults to
        ``{start_year}-01-01`` when not supplied.
    maop_psi : float, optional
        Maximum Allowable Operating Pressure (psi).  When supplied, each feature
        is classified Leak vs Rupture (rupture = Pf drops below MAOP x SF before
        depth reaches 80 % WT) and a "Repair-By Year" column is added.  When
        absent, all features fall back to "Leak" and no rupture is reported.
    safety_factor : float
        Safety factor applied to MAOP for the repair criterion (default 1.25).
    depth_cr_low, depth_cr_mid, depth_cr_high : float, optional
        Depth-banded corrosion rates (mm/yr) applied by reported depth:
        <20 % WT -> low, 20-40 % WT -> mid, >40 % WT -> high.
        Any band left as None falls back to ``depth_cr``.
    return_summary : bool
        When True, returns ``(df_result, summary_dict)`` instead of just the
        DataFrame.  The summary carries detected columns, warnings, skipped-row
        counts, and per-year exceedance statistics for UI display.

    Returns
    -------
    pd.DataFrame or (pd.DataFrame, dict)
        Original columns plus the computed assessment columns; with
        ``return_summary=True`` also a summary dict.
    """
    # Input validation — fail fast with clear messages
    if do <= 0 or tp <= 0:
        raise ValueError(f"Pipe dimensions must be positive (do={do}, tp={tp})")
    if YS <= 0 or TS <= 0:
        raise ValueError(f"Material strengths must be positive (YS={YS}, TS={TS})")
    if maop_psi is not None and maop_psi <= 0:
        raise ValueError(f"MAOP must be positive when supplied (maop_psi={maop_psi})")
    if safety_factor <= 0:
        raise ValueError(f"Safety factor must be positive (safety_factor={safety_factor})")

    summary: Dict = {"warnings": []}
    # 1. Map columns
    ili_cols = identify_ili_columns(df)
    depth_col = ili_cols.get("depth")
    length_col = ili_cols.get("length")
    feature_id_col = ili_cols.get("feature_id")

    if not depth_col or not length_col:
        logger.error(f"Required columns (depth, length) not found. Found: {list(df.columns)}")
        raise ValueError(
            f"Required columns (depth, length) not found in Excel file. Found: {list(df.columns)}"
        )

    logger.info(
        f"Using depth column: '{depth_col}', length column: '{length_col}', "
        f"feature id column: '{feature_id_col}'"
    )

    # Parse ILI reference date
    if ili_date:
        try:
            ref_date = datetime.strptime(ili_date, "%Y-%m-%d")
        except ValueError:
            ref_date = datetime(start_year, 1, 1)
    else:
        ref_date = datetime(start_year, 1, 1)

    # 2. Working copy — pre-allocate result columns in the desired output order
    df_result = df.copy()

    # Rename any pre-existing year-integer columns so our output columns don't collide.
    # This happens when the input Excel already contains Pf or SCC columns labelled with
    # year integers (e.g. a reference assessment spreadsheet with 2023-2032 columns).
    year_cols = [start_year + i for i in range(11)]
    rename_map = {}
    for col in df_result.columns:
        if isinstance(col, int) and 2000 <= col <= 2100:
            rename_map[col] = f"_ref_{col}"
    if rename_map:
        df_result = df_result.rename(columns=rename_map)
        logger.info(f"Renamed {len(rename_map)} pre-existing year columns to avoid collision: {list(rename_map.keys())}")

    # Computed columns (filled below for valid rows)
    df_result["Date to Become a Defect"] = None
    df_result["Years to Become a Defect"] = None
    df_result["Failure Mode"] = None
    df_result["Active/Inactive"] = None
    if maop_psi is not None:
        df_result["Repair-By Year (Pf < MAOP x SF)"] = None

    for yr in year_cols:
        df_result[yr] = None

    # Debug columns (appended at the end)
    df_result["Debug_Feature_ID"] = df[feature_id_col] if feature_id_col else "Not Found"
    df_result["Debug_Initial_Depth_mm"] = None
    df_result["Debug_Initial_Length_mm"] = None
    df_result["Debug_Depth_CR_mm_yr"] = None

    # 3. Identify valid rows
    depth_raw = pd.to_numeric(df[depth_col], errors='coerce')
    length_raw = pd.to_numeric(df[length_col], errors='coerce')

    valid_mask = (
        depth_raw.notna() & (depth_raw > 0) &
        length_raw.notna() & (length_raw > 0)
    )

    skipped = int((~valid_mask).sum())
    if skipped:
        logger.info(f"Skipping {skipped} rows with 0/empty depth or length.")
    logger.info(f"Valid rows: {valid_mask.sum()} out of {len(df)}")

    summary.update({
        "total_rows": int(len(df)),
        "valid_rows": int(valid_mask.sum()),
        "skipped_rows": skipped,
        "depth_column": depth_col,
        "length_column": length_col,
        "feature_id_column": feature_id_col,
        "depth_scaled_from_fraction": False,
        "wall_thickness_column": None,
        "maop_psi": maop_psi,
        "safety_factor": safety_factor if maop_psi is not None else None,
    })

    if not valid_mask.any():
        logger.warning("No valid rows found, returning empty results")
        summary["warnings"].append("No valid rows found (all depth/length values empty or non-positive).")
        return (df_result, summary) if return_summary else df_result

    # 4. Extract valid arrays and apply tolerances
    dimp_percent_vals = depth_raw[valid_mask].values
    Limp_org_vals = length_raw[valid_mask].values

    # Auto-detect depth scale: Excel sometimes stores "17%" as the fraction 0.17.
    # If all valid depth values are <= 1.5, treat them as fractions and convert to %.
    # A depth of 1.5 would mean 150 % WT which is physically impossible, so this
    # threshold is safe for any real ILI dataset.
    if dimp_percent_vals.max() <= 1.5:
        msg = (
            f"Depth values appear to be fractions (max={dimp_percent_vals.max():.4f} <= 1.5). "
            "Auto-scaled by x100 to convert to percent. "
            "If your depth column really is in percent (all features < 1.5 % WT), "
            "these results are wrong - contact the tool owner."
        )
        logger.warning(msg)
        summary["warnings"].append(msg)
        summary["depth_scaled_from_fraction"] = True
        dimp_percent_vals = dimp_percent_vals * 100.0

    # Per-row wall thickness: use a WT column from the file when present,
    # falling back to the global tp for rows where it is missing/invalid.
    tp_arr = np.full(int(valid_mask.sum()), float(tp))
    wt_col = ili_cols.get("wall_thickness")
    if wt_col and wt_col in df.columns:
        wt_raw = pd.to_numeric(df.loc[valid_mask, wt_col], errors='coerce').values
        wt_ok = ~np.isnan(wt_raw) & (wt_raw > 0)
        tp_arr[wt_ok] = wt_raw[wt_ok]
        summary["wall_thickness_column"] = wt_col
        n_wt = int(wt_ok.sum())
        logger.info(f"Using per-row wall thickness from '{wt_col}' for {n_wt} rows; global tp={tp} for the rest.")
        if n_wt:
            summary["warnings"].append(
                f"Per-row wall thickness applied from column '{wt_col}' ({n_wt} rows); "
                f"global TP {tp} mm used for the remaining {int(valid_mask.sum()) - n_wt} rows."
            )

    dimp_0 = (dimp_percent_vals + depth_tolerance) * 0.01 * tp_arr  # initial depth (mm)
    Limp_0 = Limp_org_vals + length_tolerance                        # initial length (mm)
    wall_80 = tp_arr * 0.8                                           # 80 % WT threshold (mm)

    # Depth-banded corrosion rates: <20 % WT -> low, 20-40 % -> mid, >40 % -> high.
    # Bands are chosen from the reported depth (before tolerance).  Any band not
    # supplied falls back to the single depth_cr.
    cr_low = depth_cr_low if depth_cr_low is not None else depth_cr
    cr_mid = depth_cr_mid if depth_cr_mid is not None else depth_cr
    cr_high = depth_cr_high if depth_cr_high is not None else depth_cr
    cr_arr = np.where(
        dimp_percent_vals < 20.0, cr_low,
        np.where(dimp_percent_vals <= 40.0, cr_mid, cr_high)
    ).astype(float)
    summary["corrosion_rates"] = {
        "band_lt20": cr_low, "band_20_40": cr_mid, "band_gt40": cr_high,
        "rows_lt20": int((dimp_percent_vals < 20.0).sum()),
        "rows_20_40": int(((dimp_percent_vals >= 20.0) & (dimp_percent_vals <= 40.0)).sum()),
        "rows_gt40": int((dimp_percent_vals > 40.0).sum()),
    }

    df_result.loc[valid_mask, "Debug_Initial_Depth_mm"] = np.round(dimp_0, 4)
    df_result.loc[valid_mask, "Debug_Initial_Length_mm"] = np.round(Limp_0, 4)
    df_result.loc[valid_mask, "Debug_Depth_CR_mm_yr"] = np.round(cr_arr, 4)

    # 5. "Date to Become a Defect" — when depth reaches 80 % WT under each row's rate
    with np.errstate(divide='ignore', invalid='ignore'):
        years_to_def = np.where(cr_arr > 0, (wall_80 - dimp_0) / cr_arr, np.inf)
    years_to_def = np.where(years_to_def < 0, 0.0, years_to_def)

    def _add_years(base_date: datetime, years: float) -> Optional[datetime]:
        if not np.isfinite(years):
            return None
        return base_date + timedelta(days=years * 365.25)

    dates_defect = np.array([_add_years(ref_date, y) for y in years_to_def], dtype=object)
    df_result.loc[valid_mask, "Date to Become a Defect"] = dates_defect
    df_result.loc[valid_mask, "Years to Become a Defect"] = np.round(years_to_def, 10)

    df_result.loc[valid_mask, "Active/Inactive"] = "Active"

    # 6. Calculate Pf for 11 years
    n_valid = int(valid_mask.sum())
    pf_matrix = np.full((11, n_valid), np.nan)   # numeric Pf (psi) per year
    over80_matrix = np.zeros((11, n_valid), dtype=bool)

    for i, yr in enumerate(year_cols):
        dimp_t = dimp_0 + (i * cr_arr)
        Limp_t = Limp_0 + (i * length_cr)

        res = calculate_failure_pressure(
            dimp=dimp_t,
            Limp=Limp_t,
            do=do,
            tp=tp_arr,
            YS=YS,
            TS=TS,
        )

        pf_psi = res['ans']['Pf'] * 0.14503774  # kPa → psi
        pf_matrix[i] = pf_psi
        over80_matrix[i] = (dimp_t / tp_arr) > 0.8

        results = np.round(pf_psi, 10).astype(object)
        results[over80_matrix[i]] = ">80% leak"
        df_result.loc[valid_mask, yr] = results

    # 7. Failure mode and repair-by year
    if maop_psi is not None:
        # Rupture criterion: Pf falls below MAOP x SF while still under 80 % WT.
        repair_threshold = maop_psi * safety_factor
        below_thresh = pf_matrix < repair_threshold          # (11, n)
        rupture_before_leak = np.any(below_thresh & ~over80_matrix, axis=0)
        failure_mode = np.where(rupture_before_leak, "Rupture", "Leak").astype(object)

        # Repair-by year: first year Pf < MAOP x SF OR depth > 80 % WT
        needs_repair = below_thresh | over80_matrix
        first_idx = np.argmax(needs_repair, axis=0)          # 0 when none True too
        any_repair = np.any(needs_repair, axis=0)
        repair_year = np.where(any_repair, start_year + first_idx, -1).astype(object)
        repair_year[repair_year == -1] = "Beyond horizon"
        df_result.loc[valid_mask, "Repair-By Year (Pf < MAOP x SF)"] = repair_year

        summary["rupture_count"] = int(rupture_before_leak.sum())
        summary["leak_count"] = int(n_valid - rupture_before_leak.sum())
        summary["repair_within_horizon"] = int(any_repair.sum())
    else:
        # No MAOP supplied: cannot distinguish rupture — everything reports Leak.
        failure_mode = np.full(n_valid, "Leak", dtype=object)
        summary["warnings"].append(
            "MAOP not supplied - Failure Mode defaults to 'Leak' for all features and "
            "no Repair-By Year is computed. Enter MAOP for leak/rupture classification."
        )
    df_result.loc[valid_mask, "Failure Mode"] = failure_mode

    # 8. Per-year exceedance stats + worst features for the UI summary
    summary["over_80_by_year"] = {
        int(yr): int(over80_matrix[i].sum()) for i, yr in enumerate(year_cols)
    }
    order = np.argsort(pf_matrix[0])
    worst_n = min(20, n_valid)
    feat_ids = (
        df.loc[valid_mask, feature_id_col].astype(str).values
        if feature_id_col else np.array([f"row {j}" for j in np.where(valid_mask)[0]])
    )
    summary["worst_features"] = [
        {
            "feature_id": feat_ids[j],
            "depth_pct": round(float(dimp_percent_vals[j]), 2),
            "length_mm": round(float(Limp_org_vals[j]), 1),
            "pf_year0_psi": (None if np.isnan(pf_matrix[0][j]) else round(float(pf_matrix[0][j]), 1)),
            "failure_mode": str(failure_mode[j]),
        }
        for j in order[:worst_n]
    ]

    return (df_result, summary) if return_summary else df_result
