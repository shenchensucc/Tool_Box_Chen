# 🤖 AI Development Rules

## ⚠️ CRITICAL: Read This Before Making ANY Code Changes

This document contains **mandatory constraints** for AI-assisted development to prevent over-modification, scope creep, and unintended side effects.

---

## 🎯 Core Principle: Surgical Precision

**Only modify what is explicitly requested. Nothing more.**

### The Golden Rules

1. ✅ **DO**: Make the minimum changes necessary to fulfill the request
2. ❌ **DON'T**: Refactor unrelated code "while you're at it"
3. ❌ **DON'T**: "Improve" code that wasn't asked to be changed
4. ❌ **DON'T**: Add features that weren't requested
5. ❌ **DON'T**: Change coding style in unrelated files

---

## 📍 Scope Control Guidelines

### Before Making Changes

1. **Identify the exact scope**
   - What function/module needs to be changed?
   - What files are directly involved?
   - What files should NOT be touched?

2. **Read the function-specific guide**
   - Check `docs/functions/[FUNCTION_NAME].md` for the function you're modifying
   - Understand dependencies and constraints
   - Note any "DO NOT MODIFY" warnings

3. **List affected files explicitly**
   ```
   Files to modify:
   - backend/main.py (add new endpoint)
   
   Files to READ ONLY (for understanding):
   - backend/models.py
   - frontend/pages/4_ILI_Visual_Tool.py
   
   Files to NEVER TOUCH:
   - All other files not listed above
   ```

### During Development

#### ✅ ALLOWED Modifications

- **Requested function/module**: Full modifications as needed
- **Direct dependencies**: Only if breaking changes require it
- **Import statements**: Add new imports ONLY if needed for requested feature
- **Type hints**: Fix ONLY if causing errors in modified code
- **Documentation**: Update ONLY for modified functions

#### ❌ FORBIDDEN Modifications

- **Reformatting**: Do NOT reformat code outside the requested scope
- **Style changes**: Do NOT change variable names, spacing, or quotes in unrelated code
- **"Improvements"**: Do NOT optimize, refactor, or enhance unrelated functions
- **Dependencies**: Do NOT upgrade, add, or remove packages unless explicitly requested
- **Configuration**: Do NOT change config files unless requested
- **Other functions**: Do NOT touch functions not mentioned in the request
- **Tests**: Do NOT modify unrelated test files

### Example Scenarios

#### ❌ BAD: Over-Modification
```
Request: "Add error handling to the /api/ili/preview endpoint"

Changes made:
- ✅ Added error handling to preview endpoint
- ❌ Reformatted entire backend/main.py with black
- ❌ Renamed variables in process endpoint for "consistency"
- ❌ Updated all docstrings to use Google style
- ❌ Added type hints to unrelated functions
- ❌ Reorganized imports across multiple files
```

#### ✅ GOOD: Surgical Modification
```
Request: "Add error handling to the /api/ili/preview endpoint"

Changes made:
- ✅ Added try-except block to preview_excel function
- ✅ Added specific error messages for common cases
- ✅ Updated preview_excel docstring to document errors
- ✅ Updated tests/test_backend.py to test error cases

Files touched:
- backend/main.py (lines 96-136 only)
- tests/test_backend.py (added new test function)
```

---

## 🔒 File-Level Constraints

### Backend (`backend/`)

| File | Modification Rules |
|------|-------------------|
| `main.py` | Only modify specific endpoint functions requested. Do NOT touch other endpoints. |
| `models.py` | Only add/modify models for requested features. Do NOT refactor existing models. |

### Frontend (`frontend/`)

| File/Directory | Modification Rules |
|----------------|-------------------|
| `Home.py` | Only modify if explicitly requested. This is a stable cover page. |
| `pages/1_Dashboard.py` | Only modify Dashboard if requested. Do NOT add features unprompted. |
| `pages/2_Facility.py` | Only modify Facility if requested. Do NOT implement placeholder features. |
| `pages/4_ILI_Visual_Tool.py` | Modify only requested functionality. Do NOT change visualization style. |
| `frontend_utils.py` | Add new utilities ONLY if needed by requested feature. |

### Configuration & Dependencies

| File | Modification Rules |
|------|-------------------|
| `requirements.txt` | Add packages ONLY if new feature requires them. Do NOT upgrade versions. |
| `pyproject.toml` | Modify ONLY if dependency changes are required. |
| `.pre-commit-config.yaml` | Do NOT modify unless explicitly requested. |

### Documentation

| File/Directory | Modification Rules |
|----------------|-------------------|
| `README.md` | Update ONLY if user-facing changes are made. |
| `docs/functions/*.md` | Update ONLY the guide for the function being modified. |
| `docs/CODE_REVIEW_CHECKLIST.md` | Do NOT modify unless process changes are requested. |

---

## 🧪 Testing Constraints

### DO Test

- ✅ New functionality you added
- ✅ Modified functions (regression testing)
- ✅ Error cases for changed code

### DON'T Test

- ❌ Unrelated functions that weren't changed
- ❌ Integration tests beyond the scope of changes
- ❌ Performance tests unless explicitly requested

---

## 📝 Documentation Constraints

### DO Document

- ✅ New functions/endpoints
- ✅ Changed behavior in modified functions
- ✅ New parameters or return values
- ✅ New error conditions

### DON'T Document

- ❌ Unrelated functions
- ❌ Reformatting existing documentation for style
- ❌ Adding documentation to unmodified code

---

## 🚨 Anti-Patterns to Avoid

### 1. The "While I'm Here" Syndrome
```python
# ❌ BAD
def add_new_feature():
    # Added the requested feature
    new_feature()
    
    # "While I'm here, let me also..."
    refactor_unrelated_function()  # ❌ NO!
    fix_typo_in_comment()          # ❌ NO!
    reorganize_imports()            # ❌ NO!
```

### 2. The "This Should Be Better" Trap
```python
# ❌ BAD
# Request: Fix bug in calculate_stats
def calculate_stats(series: pd.Series) -> ColumnStats:
    # Fixed the bug as requested
    desc = series.describe()
    
    # "This function name is not very clear, let me rename it"
    # Then renamed across 15 files... ❌ NO!
```

### 3. The "Future-Proofing" Pitfall
```python
# ❌ BAD
# Request: Add metal_loss_column parameter
def process_data(distance_column: str, metal_loss_column: str):
    # Added metal_loss_column as requested
    
    # "Let me also add temperature, pressure, corrosion parameters
    # for future features..." ❌ NO!
```

### 4. The "Consistency Crusade"
```python
# ❌ BAD
# Request: Update ILI tool error handling
# Files modified:
# - pages/4_ILI_Visual_Tool.py (✅ requested)
# - pages/1_Dashboard.py (❌ "for consistency")
# - pages/2_Facility.py (❌ "for consistency")
# - frontend_utils.py (❌ "for consistency")
```

---

## ✅ Checklist Before Committing

Before finalizing any code changes, verify:

- [ ] I only modified files directly related to the request
- [ ] I did NOT refactor unrelated code
- [ ] I did NOT change coding style outside my scope
- [ ] I did NOT add features that weren't requested
- [ ] I read the function-specific guide for what I changed
- [ ] I updated ONLY the documentation for changed code
- [ ] I added tests ONLY for my changes
- [ ] I can explain why EVERY file I modified needed to be modified

---

## 🎓 Training Prompts for AI

When starting a new task, the AI should ask itself:

1. **What is the minimal scope?**
   - "The user wants X. What is the absolute minimum I need to change to achieve X?"

2. **What should I NOT touch?**
   - "What files, functions, or modules are explicitly out of scope?"

3. **What might I be tempted to 'improve'?**
   - "What unrelated code looks 'messy' but I should leave alone?"

4. **Have I read the function guide?**
   - "Did I read `docs/functions/[FUNCTION].md` before modifying?"

5. **Can I justify every change?**
   - "If someone asks why I changed line X, can I point to the original request?"

---

## 🔄 Iterative Development Process

```
1. READ REQUEST
   ↓
2. IDENTIFY SCOPE (write it down!)
   ↓
3. READ FUNCTION GUIDE (docs/functions/)
   ↓
4. LIST FILES TO MODIFY (explicit list)
   ↓
5. MAKE CHANGES (only to listed files)
   ↓
6. VERIFY SCOPE (did I stay within bounds?)
   ↓
7. TEST CHANGES (only modified functionality)
   ↓
8. DOCUMENT CHANGES (only modified code)
   ↓
9. COMMIT (with clear scope description)
```

---

## 📊 Measuring Success

A successful AI-assisted change should:

- ✅ Fulfill the exact request
- ✅ Modify minimal number of files
- ✅ Have clear justification for every change
- ✅ Pass all existing tests
- ✅ Not break unrelated functionality

A failed AI-assisted change has:

- ❌ Changes outside the requested scope
- ❌ "Improvements" that weren't asked for
- ❌ Reformatted code unrelated to the task
- ❌ New features beyond the request
- ❌ Style changes across multiple files

---

## 🚫 Common Excuses to REJECT

| Excuse | Response |
|--------|----------|
| "I'm making it more consistent" | ❌ Only if explicitly requested |
| "This follows best practices" | ❌ Only change what's requested |
| "I noticed this other issue" | ❌ File a separate issue/request |
| "This will make future changes easier" | ❌ YAGNI - You Aren't Gonna Need It |
| "The code was already messy" | ❌ Not your scope to clean |
| "It's a small change" | ❌ Still outside requested scope |

---

## 📞 When in Doubt

**ASK** before making changes outside the explicit request.

**Default to NO** when unsure if something should be modified.

**Remember**: Under-modification is better than over-modification.

---

**This document is mandatory reading before ANY code modification.**

Last Updated: October 2025
