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
) -> pd.DataFrame:
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

    Returns
    -------
    pd.DataFrame
        Original columns plus the computed assessment columns.
    """
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

    wall_80 = tp * 0.8  # 80 % WT threshold (mm)

    # Computed columns (filled below for valid rows)
    df_result["Date to Become a Defect"] = None
    df_result["Years to Become a Defect"] = None
    df_result["Failure Mode"] = None
    df_result["Active/Inactive"] = None

    # Year Pf columns: 11 years inclusive (i=0 … 10)
    year_cols = [start_year + i for i in range(11)]
    for yr in year_cols:
        df_result[yr] = None

    # Debug columns (appended at the end)
    df_result["Debug_Feature_ID"] = df[feature_id_col] if feature_id_col else "Not Found"
    df_result["Debug_Initial_Depth_mm"] = None
    df_result["Debug_Initial_Length_mm"] = None

    # 3. Identify valid rows
    depth_raw = pd.to_numeric(df[depth_col], errors='coerce')
    length_raw = pd.to_numeric(df[length_col], errors='coerce')

    valid_mask = (
        depth_raw.notna() & (depth_raw > 0) &
        length_raw.notna() & (length_raw > 0)
    )

    skipped = (~valid_mask).sum()
    if skipped:
        logger.info(f"Skipping {skipped} rows with 0/empty depth or length.")
    logger.info(f"Valid rows: {valid_mask.sum()} out of {len(df)}")

    if not valid_mask.any():
        logger.warning("No valid rows found, returning empty results")
        return df_result

    # 4. Extract valid arrays and apply tolerances
    dimp_percent_vals = depth_raw[valid_mask].values
    Limp_org_vals = length_raw[valid_mask].values

    dimp_0 = (dimp_percent_vals + depth_tolerance) * 0.01 * tp  # initial depth (mm)
    Limp_0 = Limp_org_vals + length_tolerance                    # initial length (mm)

    df_result.loc[valid_mask, "Debug_Initial_Depth_mm"] = np.round(dimp_0, 4)
    df_result.loc[valid_mask, "Debug_Initial_Length_mm"] = np.round(Limp_0, 4)

    # 5. "Date to Become a Defect" — when depth reaches 80 % WT under constant depth_cr
    if depth_cr > 0:
        # Years until dimp_0[i] reaches wall_80 under constant depth_cr
        years_to_def = (wall_80 - dimp_0) / depth_cr
        # Features already at/above 80 % WT get 0 years (effectively immediate)
        years_to_def = np.where(years_to_def < 0, 0.0, years_to_def)

        def _add_years(base_date: datetime, years: float) -> datetime:
            return base_date + timedelta(days=years * 365.25)

        dates_defect = np.array([_add_years(ref_date, y) for y in years_to_def])
        df_result.loc[valid_mask, "Date to Become a Defect"] = dates_defect
        df_result.loc[valid_mask, "Years to Become a Defect"] = np.round(years_to_def, 10)
    else:
        df_result.loc[valid_mask, "Years to Become a Defect"] = np.inf
        df_result.loc[valid_mask, "Date to Become a Defect"] = None

    # Metal loss always has Leak failure mode; all features assumed Active
    df_result.loc[valid_mask, "Failure Mode"] = "Leak"
    df_result.loc[valid_mask, "Active/Inactive"] = "Active"

    # 6. Calculate Pf for 11 years
    for i, yr in enumerate(year_cols):
        dimp_t = dimp_0 + (i * depth_cr)
        Limp_t = Limp_0 + (i * length_cr)

        res = calculate_failure_pressure(
            dimp=dimp_t,
            Limp=Limp_t,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS,
        )

        pf_psi = res['ans']['Pf'] * 0.14503774  # kPa → psi
        results = np.round(pf_psi, 10).astype(object)

        # Mark features beyond 80 % WT
        is_over = (dimp_t / tp) > 0.8
        results[is_over] = ">80% leak"

        df_result.loc[valid_mask, yr] = results

    return df_result
