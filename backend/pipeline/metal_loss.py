"""
Metal Loss Assessment Calculations
Translated from R package 'mla' to Python
"""
import numpy as np
from typing import Dict, List, Optional, Union


def calculate_folias_factor(
    do: float,
    tp: float,
    Limp: float,
    method: str = "mb31g",
    z: Optional[float] = None
) -> Union[float, np.ndarray]:
    """
    Calculate Folias/bulging factor for metal loss assessment.
    
    Translated from R function fMfolias().
    
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
    Limp: float,
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
    
    Translated from R function fmla().
    
    Parameters:
    -----------
    dimp : float, list, or ndarray
        Depth of the defect (mm)
    Limp : float
        Length of the defect (mm)
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
    
    # Calculate Folias factor
    Mfolias_values = np.array([calculate_folias_factor(do, tp, Limp, method) for _ in range(n)])
    
    # Initialize remaining strength factor
    Rs = np.full(n, np.nan)
    
    # Calculate remaining strength based on method
    if method == "b31g":
        # For z <= 20
        valid_idx = ~np.isnan(Mfolias_values)
        Rs[valid_idx] = (1 - (2/3) * d_t[valid_idx]) / (1 - (2/3) * d_t[valid_idx] / Mfolias_values[valid_idx])
        # For z > 20
        invalid_idx = np.isnan(Mfolias_values)
        Rs[invalid_idx] = 1 - d_t[invalid_idx]
        
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
    
    cutoff_month_low = cutoff_low[0] if len(cutoff_low) > 0 else month_CR
    cutoff_month_ave = cutoff_ave[0] if len(cutoff_ave) > 0 else month_CR
    cutoff_month_high = cutoff_high[0] if len(cutoff_high) > 0 else month_CR
    
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

