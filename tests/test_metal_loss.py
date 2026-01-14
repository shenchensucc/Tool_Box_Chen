"""
Unit tests for metal loss assessment calculations
# Tests are based on standard validation cases
"""
import pytest
import numpy as np
from backend.pipeline.metal_loss import (
    calculate_folias_factor,
    calculate_failure_pressure,
    assess_metal_loss_feature
)


class TestFoliasFactorCalculations:
    """Test Folias factor calculations for different methods"""
    
    def test_modified_b31g_z_greater_than_50(self):
        """Test Modified B31G with z > 50"""
        do = 273.1  # mm
        tp = 5.16  # mm
        Limp = 300  # mm
        
        # Calculate z
        z = Limp ** 2 / (do * tp)
        assert z > 50, "Test requires z > 50"
        
        # Expected Folias factor when z > 50
        expected_Mfolias = 3.3 + 0.032 * z
        
        # Calculate using our function
        result = calculate_folias_factor(do, tp, Limp, method="mb31g")
        
        assert np.isclose(result, expected_Mfolias), \
            f"Folias factor mismatch: {result} != {expected_Mfolias}"
    
    def test_modified_b31g_z_less_than_or_equal_50(self):
        """Test Modified B31G with z <= 50"""
        do = 273.1  # mm
        tp = 5.16  # mm
        Limp = 200  # mm
        
        # Calculate z
        z = Limp ** 2 / (do * tp)
        assert z <= 50, "Test requires z <= 50"
        
        # Expected Folias factor when z <= 50
        expected_Mfolias = (1 + 0.6275 * z - 0.003375 * z ** 2) ** 0.5
        
        # Calculate using our function
        result = calculate_folias_factor(do, tp, Limp, method="mb31g")
        
        assert np.isclose(result, expected_Mfolias), \
            f"Folias factor mismatch: {result} != {expected_Mfolias}"
    
    def test_b31g_method(self):
        """Test original B31G method (z <= 20)"""
        do = 273.1
        tp = 5.16
        Limp = 100  # Small length to ensure z <= 20
        
        z = Limp ** 2 / (do * tp)
        assert z <= 20, "Test requires z <= 20 for B31G"
        
        expected_Mfolias = (1 + 0.80 * z) ** 0.5
        result = calculate_folias_factor(do, tp, Limp, method="b31g")
        
        assert np.isclose(result, expected_Mfolias), \
            f"B31G Folias factor mismatch: {result} != {expected_Mfolias}"
    
    def test_ng18_method(self):
        """Test NG-18 method"""
        do = 273.1
        tp = 5.16
        Limp = 200
        
        z = Limp ** 2 / (do * tp)
        expected_Mfolias = (1 + 0.6275 * z - 0.003375 * z ** 2) ** 0.5
        result = calculate_folias_factor(do, tp, Limp, method="ng18")
        
        assert np.isclose(result, expected_Mfolias), \
            f"NG-18 Folias factor mismatch: {result} != {expected_Mfolias}"


class TestFailurePressureCalculations:
    """Test failure pressure calculations - matching expected results"""
    
    def test_modified_b31g_z_greater_than_50(self):
        """
        # Standard test case
        Test modified B31G with z > 50
        """
        # Test parameters from R
        do = 273.1  # 10.75"
        tp = 5.16  # 0.203"
        SMYS = 359  # MPa
        Sflow = SMYS + 69  # MPa
        dimp = 0.50 * tp  # 50% depth
        Limp = 300  # mm
        YS = 359  # MPa
        TS = 455  # MPa
        
        # Calculate expected values using R formulas
        d_t = dimp / tp
        z = Limp ** 2 / (do * tp)
        
        # Modified B31G: z > 50
        assert z > 50, "Test requires z > 50"
        Mbulge = 3.3 + 0.032 * z
        
        Rs = (1 - 0.85 * d_t) / (1 - 0.85 * d_t / Mbulge)
        Po = 2 * Sflow / (do / tp)
        expected_Pf = Po * Rs * 1000  # kPa
        
        # Calculate using our function
        result = calculate_failure_pressure(
            dimp=dimp,
            Limp=Limp,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS
        )
        
        calculated_Pf = result['ans']['Pf'][0]
        
        # Assert match with expected results
        assert np.isclose(calculated_Pf, expected_Pf, rtol=1e-6), \
            f"Failure pressure mismatch: {calculated_Pf} != {expected_Pf}"
        
        print(f"✓ Test passed: Pf = {calculated_Pf:.2f} kPa (expected: {expected_Pf:.2f} kPa)")
    
    def test_modified_b31g_z_less_than_or_equal_50(self):
        """
        # Standard test case
        Test modified B31G with z <= 50
        """
        # Test parameters from R
        do = 273.1  # 10.75"
        tp = 5.16  # 0.203"
        SMYS = 359  # MPa
        Sflow = SMYS + 69  # MPa
        dimp = 0.50 * tp  # 50% depth
        Limp = 200  # mm
        YS = 359  # MPa
        TS = 455  # MPa
        
        # Calculate expected values using R formulas
        d_t = dimp / tp
        z = Limp ** 2 / (do * tp)
        
        # Modified B31G: z <= 50
        assert z <= 50, "Test requires z <= 50"
        Mbulge = (1 + 0.6275 * z - 0.003375 * z ** 2) ** 0.5
        
        Rs = (1 - 0.85 * d_t) / (1 - 0.85 * d_t / Mbulge)
        Po = 2 * Sflow / (do / tp)
        expected_Pf = Po * Rs * 1000  # kPa
        
        # Calculate using our function
        result = calculate_failure_pressure(
            dimp=dimp,
            Limp=Limp,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS
        )
        
        calculated_Pf = result['ans']['Pf'][0]
        
        # Assert match with expected results
        assert np.isclose(calculated_Pf, expected_Pf, rtol=1e-6), \
            f"Failure pressure mismatch: {calculated_Pf} != {expected_Pf}"
        
        print(f"✓ Test passed: Pf = {calculated_Pf:.2f} kPa (expected: {expected_Pf:.2f} kPa)")
    
    def test_multiple_depths(self):
        """Test with array of depths (growth over time)"""
        do = 273.1
        tp = 5.16
        Limp = 200
        YS = 359
        TS = 455
        
        # Multiple depth values (simulating growth)
        depths = [0.3 * tp, 0.4 * tp, 0.5 * tp, 0.6 * tp]
        
        result = calculate_failure_pressure(
            dimp=depths,
            Limp=Limp,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS
        )
        
        # Check that we got results for all depths
        assert len(result['ans']['Pf']) == len(depths), \
            "Should return failure pressure for each depth"
        
        # Check that failure pressure decreases as depth increases
        Pf_values = result['ans']['Pf']
        for i in range(len(Pf_values) - 1):
            assert Pf_values[i] > Pf_values[i+1], \
                "Failure pressure should decrease as defect depth increases"
        
        print(f"✓ Test passed: Multiple depths calculated correctly")
    
    def test_depth_to_thickness_warning(self):
        """Test warning for d/t > 80%"""
        do = 273.1
        tp = 5.16
        Limp = 200
        YS = 359
        TS = 455
        dimp = 0.85 * tp  # 85% depth (exceeds 80% limit)
        
        result = calculate_failure_pressure(
            dimp=dimp,
            Limp=Limp,
            do=do,
            tp=tp,
            YS=YS,
            TS=TS
        )
        
        # Check that warning was generated
        assert len(result['warnings']) > 0, \
            "Should generate warning for d/t > 80%"
        assert "d_t ratio > 80%" in result['warnings'][0], \
            "Warning should mention d/t ratio exceeds 80%"
        
        print(f"✓ Test passed: Warning generated for d/t > 80%")


class TestCompleteAssessment:
    """Test complete metal loss feature assessment"""
    
    def test_full_assessment_scenario(self):
        """Test complete assessment matching validation example"""
        # Parameters from PNG_Metal_Loss_Feature_Assessment.Rmd
        do = 273.1  # mm
        tp = 6.35  # mm
        YS = 359  # MPa
        TS = 455  # MPa
        dimp_org_percent = 41  # %
        Limp_org = 361  # mm
        date_ILI = "2023-07-27"
        ILI_dimp_tolerance = 15  # %
        ILI_Limp_tolerance = 0  # mm
        CR_low = 0.196  # mm/yr
        CR_ave = 0.245  # mm/yr
        CR_high = 0.452  # mm/yr
        month_CR = 48  # months
        
        result = assess_metal_loss_feature(
            do=do,
            tp=tp,
            YS=YS,
            TS=TS,
            dimp_org_percent=dimp_org_percent,
            Limp_org=Limp_org,
            date_ILI=date_ILI,
            ILI_dimp_tolerance=ILI_dimp_tolerance,
            ILI_Limp_tolerance=ILI_Limp_tolerance,
            CR_low=CR_low,
            CR_ave=CR_ave,
            CR_high=CR_high,
            month_CR=month_CR,
            feature_ID="7",
            vendor_ILI="ROSEN MFL-C"
        )
        
        # Verify structure
        assert 'inputs' in result
        assert 'calculated' in result
        assert 'depth_arrays' in result
        assert 'sop_arrays' in result
        assert 'cutoff_months' in result
        
        # Verify arrays have correct length
        assert len(result['depth_arrays']['low']) == month_CR
        assert len(result['depth_arrays']['ave']) == month_CR
        assert len(result['depth_arrays']['high']) == month_CR
        
        # Verify SOP arrays
        assert len(result['sop_arrays']['low']) == month_CR
        assert len(result['sop_arrays']['ave']) == month_CR
        assert len(result['sop_arrays']['high']) == month_CR
        
        # Verify depth increases over time
        depth_low = result['depth_arrays']['low']
        assert depth_low[0] < depth_low[-1], \
            "Depth should increase over time"
        
        # Verify SOP decreases over time
        sop_low = result['sop_arrays']['low']
        assert sop_low[0] > sop_low[-1], \
            "SOP should decrease over time"
        
        # Verify 80% wall thickness calculation
        wall_80 = result['calculated']['wall_thickness_80']
        assert wall_80 == tp * 0.8, \
            "80% wall thickness calculated incorrectly"
        
        print(f"✓ Test passed: Complete assessment scenario")
        print(f"  Initial depth: {depth_low[0]:.2f} mm")
        print(f"  Final depth: {depth_low[-1]:.2f} mm")
        print(f"  Initial SOP: {sop_low[0]:.2f} psi")
        print(f"  Final SOP: {sop_low[-1]:.2f} psi")
    
    def test_cutoff_calculation(self):
        """Test that cutoff months are calculated correctly"""
        # Use high growth rate to ensure cutoff is reached
        result = assess_metal_loss_feature(
            do=273.1,
            tp=6.35,
            YS=359,
            TS=455,
            dimp_org_percent=60,  # Start at 60% depth
            Limp_org=361,
            date_ILI="2023-07-27",
            ILI_dimp_tolerance=10,
            ILI_Limp_tolerance=0,
            CR_low=0.5,  # High growth rate
            CR_ave=1.0,
            CR_high=2.0,
            month_CR=24
        )
        
        # Verify cutoff months are within range
        cutoff_high = result['cutoff_months']['high']
        assert 0 <= cutoff_high <= 24, \
            f"Cutoff month should be within projection period: {cutoff_high}"
        
        # Verify cutoff logic: depth at cutoff should be >= 80% wall thickness
        depth_at_cutoff = result['depth_arrays']['high'][cutoff_high - 1]
        wall_80 = result['calculated']['wall_thickness_80']
        
        # Allow small tolerance due to monthly increments
        assert depth_at_cutoff >= wall_80 * 0.95, \
            f"Depth at cutoff ({depth_at_cutoff:.2f}) should be near 80% wall thickness ({wall_80:.2f})"
        
        print(f"✓ Test passed: Cutoff calculation")
        print(f"  Cutoff month: {cutoff_high}")
        print(f"  Depth at cutoff: {depth_at_cutoff:.2f} mm")
        print(f"  80% wall thickness: {wall_80:.2f} mm")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])





