# 🧪 Metal Loss Assessment - Testing Guide

## Quick Test with Button Feature

I've added **three test case buttons** at the top of the Metal Loss Assessment page that automatically load R package test cases. This makes testing super easy!

## 🚀 How to Use Test Case Buttons

### Step 1: Start the Application

**Terminal 1 - Backend:**
```powershell
cd C:\Users\cshen\Documents\Tool_Box_Chen
uv run uvicorn backend.main:app --reload
```

**Terminal 2 - Frontend:**
```powershell
cd C:\Users\cshen\Documents\Tool_Box_Chen
streamlit run frontend/Home.py
```

### Step 2: Navigate to Metal Loss Assessment

1. Open browser to `http://localhost:8501`
2. Sidebar → **🛢️ Pipeline** (expand it)
3. Click **🔬 Metal Loss Assessment**

### Step 3: Use Test Case Buttons

At the top of the page, you'll see:

```
🧪 Load R Package Test Cases (click to expand)
```

Click to expand it, then you'll see **three buttons**:

---

### 🔘 Button 1: Test Case 1: z > 50

**What it does:**
- Loads parameters from R package test case where z > 50
- Tests the **linear Folias factor formula** (3.3 + 0.032z)
- This is the simplified formula used for long defects

**Parameters loaded:**
- Pipe: OD=273.1mm, WT=5.16mm
- Material: YS=359 MPa, TS=455 MPa
- Defect: 50% depth, **300mm length** (long defect)
- Tolerances: 0% (for exact comparison with R)
- Growth rates: 0 mm/yr (single point calculation)
- Projection: 1 month

**Click the button** → Page will refresh with values loaded → Scroll down and click "🚀 Run Assessment"

**Expected results:**
- Initial failure pressure should match R calculation
- Since growth rates are 0, all three lines overlap
- z value is > 50, so linear Folias factor is used

---

### 🔘 Button 2: Test Case 2: z ≤ 50

**What it does:**
- Loads parameters from R package test case where z ≤ 50
- Tests the **polynomial Folias factor formula** √(1 + 0.6275z - 0.003375z²)
- This is the more accurate formula for shorter defects

**Parameters loaded:**
- Pipe: OD=273.1mm, WT=5.16mm
- Material: YS=359 MPa, TS=455 MPa
- Defect: 50% depth, **200mm length** (shorter defect)
- Tolerances: 0% (for exact comparison with R)
- Growth rates: 0 mm/yr (single point calculation)
- Projection: 1 month

**Click the button** → Page will refresh → Scroll down and click "🚀 Run Assessment"

**Expected results:**
- Different failure pressure than Test Case 1
- z value is ≤ 50, so polynomial Folias factor is used
- Should exactly match R package output

---

### 🔘 Button 3: R Markdown Example

**What it does:**
- Loads the **complete assessment scenario** from your R markdown file
- Shows realistic assessment with growth over time
- Full 48-month projection with three growth scenarios

**Parameters loaded:**
- Pipe: NPS 10, OD=273.1mm, WT=6.35mm
- Material: Grade X52 (YS=359 MPa, TS=455 MPa)
- Defect: 41% depth, 361mm length
- Feature: ID "7", ROSEN MFL-C vendor
- Tolerances: 15% depth, 0mm length
- Growth rates: 0.196/0.245/0.452 mm/yr (Low/Ave/High)
- Projection: 48 months

**Click the button** → Preset scenario changes to "NPS 10 - Sch 40 - Grade X52" → Click "🚀 Run Assessment"

**Expected results:**
- Three distinct growth scenarios visible
- Depth increases over 48 months
- SOP decreases over time
- 80% wall thickness cutoff dates calculated
- All three charts display properly
- Matches your R markdown output!

---

## 📊 Visual Results to Expect

### Test Cases 1 & 2 (Single Point Calculations)

**What you'll see:**
- All three growth lines overlap (since CR = 0)
- Single point failure pressure calculation
- Simple charts (flat lines since no growth)
- Data tables show single month

**Why useful:**
- Validates core calculation functions
- Compares Python vs R exactly
- No time-based complexity

### Test Case 3 (Full Assessment)

**What you'll see:**
- **Depth Growth Chart:**
  - Three diverging lines (green, orange, red)
  - Red dashed line at 80% wall thickness
  - Depth increases over time
  
- **SOP Decay Chart:**
  - Three lines decreasing over time
  - Green line (low growth) stays highest
  - Red line (high growth) drops fastest
  - 800 psi threshold line
  
- **SOP with Cutoff Chart:**
  - Lines stop at different months
  - High growth rate stops first
  - Shows when defect reaches 80% wall thickness

**Why useful:**
- Demonstrates full functionality
- Shows realistic assessment scenario
- Tests time-based projections

---

## 🔄 Resetting After Test

After loading a test case, you'll see a button:

```
🔄 Clear Test Case and Reset
```

Click this to:
- Clear the loaded test case
- Reset to default values
- Start fresh with new parameters

---

## ✅ Verification Checklist

After running each test case:

**Basic Checks:**
- [ ] All input fields populated correctly
- [ ] No error messages in browser or terminal
- [ ] All three charts display
- [ ] Data tables show values

**Test Case 1 (z > 50):**
- [ ] z value is > 50 (check: z = L²/(D·t) = 300²/(273.1·5.16) ≈ 63.8)
- [ ] Failure pressure calculated
- [ ] Results are consistent

**Test Case 2 (z ≤ 50):**
- [ ] z value is ≤ 50 (check: z = L²/(D·t) = 200²/(273.1·5.16) ≈ 28.4)
- [ ] Failure pressure is DIFFERENT from Test Case 1
- [ ] Results are consistent

**Test Case 3 (R Markdown):**
- [ ] Three distinct growth scenarios visible
- [ ] Depth increases monotonically
- [ ] SOP decreases monotonically
- [ ] Cutoff months calculated (should be different for each scenario)
- [ ] Word export works

---

## 🎯 Expected Values (for Verification)

### Test Case 1 (z > 50, Limp=300mm)
```
z = 300²/(273.1 × 5.16) ≈ 63.83 (> 50 ✓)
Folias factor M = 3.3 + 0.032 × 63.83 ≈ 5.34
d/t = 0.50
Rs = (1 - 0.85 × 0.50) / (1 - 0.85 × 0.50 / 5.34) ≈ 0.686
Sflow = 359 + 69 = 428 MPa
Pf ≈ 2 × 428 × (5.16/273.1) × 0.686 × 1000 ≈ 11,103 kPa
```

### Test Case 2 (z ≤ 50, Limp=200mm)
```
z = 200²/(273.1 × 5.16) ≈ 28.37 (≤ 50 ✓)
Folias factor M = √(1 + 0.6275 × 28.37 - 0.003375 × 28.37²) ≈ 4.20
d/t = 0.50
Rs = (1 - 0.85 × 0.50) / (1 - 0.85 × 0.50 / 4.20) ≈ 0.657
Pf ≈ 2 × 428 × (5.16/273.1) × 0.657 × 1000 ≈ 10,632 kPa
```

**Note:** Test Case 1 has higher failure pressure (longer defect uses linear approximation)

---

## 💡 Tips

1. **Start with Test Cases 1 & 2** - Quick validation of core math
2. **Then try Test Case 3** - Full feature demonstration
3. **Use "Clear Test Case"** button between tests
4. **Check backend terminal** for any error messages
5. **Try Word export** with Test Case 3 to see full report

---

## 🐛 Troubleshooting

**Buttons don't work:**
- Refresh the page (Ctrl+R or F5)
- Check that backend is running
- Look at browser console (F12) for errors

**Values don't change:**
- Make sure page refreshed after clicking button
- Check that you clicked "🚀 Run Assessment" after loading test case
- Try clicking "Clear Test Case" then reload

**Charts don't appear:**
- Verify backend is running (check terminal)
- Check network tab in browser dev tools
- Look for error messages

**Word export fails:**
- Make sure kaleido is installed: `pip install kaleido`
- Try with Test Case 3 (has growth over time)
- Check backend terminal for errors

---

## 📝 Summary

The test case buttons make it incredibly easy to:
- ✅ Validate Python implementation against R package
- ✅ Demonstrate functionality to stakeholders
- ✅ Quick regression testing after code changes
- ✅ Learn how different parameters affect results

Just click → Run → Compare with expected values!

