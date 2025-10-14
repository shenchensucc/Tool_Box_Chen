# 📂 Documentation File Management Guide

## 🎯 Purpose

This guide helps maintain a clean, organized documentation structure by identifying and removing duplicate or unnecessary documentation files.

---

## 📋 Current Documentation Structure

### ✅ Root Level (User-Facing)

These files should **remain at project root** for easy user access:

| File | Purpose | Keep? | Reason |
|------|---------|-------|--------|
| `README.md` | Main project documentation | ✅ KEEP | Entry point for users, linked from GitHub |
| `QUICK_START.md` | Quick setup guide (3 steps) | ✅ KEEP | Quick reference for users getting started |
| `PROJECT_SUMMARY.md` | Project overview (legacy) | ❌ DELETE | **Redundant** - Content now in `docs/` |

### ✅ Documentation Folder (`docs/`)

These files should **stay in `docs/` folder**:

| File | Purpose | Keep? |
|------|---------|-------|
| `docs/README.md` | Documentation hub | ✅ KEEP |
| `docs/ARCHITECTURE.md` | System architecture | ✅ KEEP |
| `docs/DEVELOPMENT_GUIDE.md` | Development practices | ✅ KEEP |
| `docs/AI_DEVELOPMENT_RULES.md` | AI development constraints | ✅ KEEP |
| `docs/CODE_REVIEW_CHECKLIST.md` | Code review standards | ✅ KEEP |
| `docs/PROJECT_STRUCTURE.md` | File organization | ✅ KEEP |
| `docs/DOCUMENTATION_SETUP_COMPLETE.md` | Setup summary | ✅ KEEP |
| `docs/FILE_MANAGEMENT.md` | This file | ✅ KEEP |

### ✅ Function Guides (`docs/functions/`)

| File | Purpose | Keep? |
|------|---------|-------|
| `docs/functions/ILI_VISUAL_TOOL.md` | ILI tool guide | ✅ KEEP |
| `docs/functions/DASHBOARD.md` | Dashboard guide | ✅ KEEP |
| `docs/functions/FACILITY.md` | Facility tools guide | ✅ KEEP |
| `docs/functions/BACKEND_API.md` | Backend API guide | ✅ KEEP |
| `docs/functions/FRONTEND_COMPONENTS.md` | Frontend patterns | ✅ KEEP |

---

## 🗑️ Files to Delete

### Identified for Deletion

**`PROJECT_SUMMARY.md`** (root level)
- **Why delete**: Content is redundant with:
  - `docs/DOCUMENTATION_SETUP_COMPLETE.md` (has more complete summary)
  - `docs/PROJECT_STRUCTURE.md` (has file structure)
  - `docs/ARCHITECTURE.md` (has tech stack)
  - Main `README.md` (has user-facing overview)
- **Action**: Delete immediately
- **Impact**: None - all information preserved in `docs/` folder

---

## 🔍 How to Identify Duplicate Documentation

### Checklist for Evaluating Files

When you find a documentation file, ask:

1. **Is it user-facing?**
   - YES → Keep at root (e.g., README.md, QUICK_START.md)
   - NO → Should be in `docs/`

2. **Is it redundant?**
   - Check if content exists in `docs/` folder
   - If yes, and `docs/` version is more complete → Delete
   - If yes, but this version is better → Move to `docs/` and delete old

3. **Is it temporary?**
   - Setup notes, scratch files, etc. → Delete
   - Outdated guides → Delete or update

4. **Is it version-specific?**
   - Old migration guides (already migrated) → Delete
   - Legacy documentation (system changed) → Delete

### Common Duplicate Patterns

| Pattern | Action |
|---------|--------|
| `GUIDE.md` at root + `docs/GUIDE.md` | Keep `docs/` version, delete root |
| Multiple "overview" files | Consolidate into one, delete others |
| Legacy + new versions | Keep new, delete legacy (note in changelog) |
| Draft files (e.g., `DRAFT_*.md`) | Delete after finalizing |

---

## 🧹 Cleaning Process

### Step 1: List All Documentation Files

```bash
# List all .md files in project
find . -name "*.md" -type f

# Or on Windows PowerShell
Get-ChildItem -Path . -Filter "*.md" -Recurse | Select-Object FullName
```

### Step 2: Categorize Files

Create a checklist:
```
[ ] README.md - Root, user-facing ✅ KEEP
[ ] QUICK_START.md - Root, user-facing ✅ KEEP
[ ] PROJECT_SUMMARY.md - Root, redundant ❌ DELETE
[ ] docs/README.md - Documentation hub ✅ KEEP
[ ] docs/*.md - All essential ✅ KEEP
[ ] docs/functions/*.md - All function guides ✅ KEEP
```

### Step 3: Verify No Dependencies

Before deleting any file, check for references:

```bash
# Search for references to file (example: PROJECT_SUMMARY.md)
grep -r "PROJECT_SUMMARY" .

# Or on Windows PowerShell
Select-String -Path . -Pattern "PROJECT_SUMMARY" -Recurse
```

### Step 4: Delete Safely

```bash
# Delete file
rm PROJECT_SUMMARY.md

# Or on Windows
Remove-Item PROJECT_SUMMARY.md
```

### Step 5: Update References

If any files referenced the deleted file, update them to point to the new location.

---

## 📝 Maintenance Schedule

### Weekly Check
- [ ] Look for new .md files in root
- [ ] Check for draft files left behind
- [ ] Verify all docs are in correct locations

### Monthly Review
- [ ] Review all documentation for redundancy
- [ ] Check for outdated information
- [ ] Consolidate similar guides if needed

### After Major Changes
- [ ] Update affected documentation
- [ ] Remove deprecated guides
- [ ] Create migration notes if needed

---

## 🚦 Decision Tree: Keep or Delete?

```
New .md file found
    │
    ├─→ Is it in docs/ folder?
    │   ├─→ YES: Check purpose
    │   │   ├─→ Unique content? → KEEP
    │   │   └─→ Duplicate? → DELETE
    │   └─→ NO: Should it be user-facing?
    │       ├─→ YES: Keep at root (README, QUICK_START)
    │       └─→ NO: Move to docs/ or DELETE
    │
    ├─→ Does content exist elsewhere?
    │   ├─→ YES: Which is better?
    │   │   ├─→ This one → DELETE other, keep this
    │   │   └─→ Other one → DELETE this
    │   └─→ NO: Is it useful?
    │       ├─→ YES → KEEP (move to docs/ if needed)
    │       └─→ NO → DELETE
    │
    └─→ Is it temporary/draft?
        ├─→ YES → DELETE
        └─→ NO → Evaluate by purpose
```

---

## 📋 Documentation Standards

### Root Level Rules

**Only these types of files at root:**
1. **README.md** - Main project documentation
2. **QUICK_START.md** - Quick setup guide
3. **CHANGELOG.md** - Version history (if maintained)
4. **CONTRIBUTING.md** - Contribution guidelines (if needed)
5. **LICENSE.md** - License file

**Everything else goes in `docs/`!**

### Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Main docs | `UPPERCASE.md` | `ARCHITECTURE.md` |
| Function guides | `FUNCTION_NAME.md` | `ILI_VISUAL_TOOL.md` |
| Feature docs | `lowercase_with_underscores.md` | `file_management.md` |
| Temporary | `DRAFT_*.md` or `WIP_*.md` | `DRAFT_new_feature.md` |

### File Locations

| Content Type | Location | Example |
|--------------|----------|---------|
| User-facing overview | Root | `README.md` |
| Architecture/design | `docs/` | `docs/ARCHITECTURE.md` |
| Function-specific | `docs/functions/` | `docs/functions/ILI_VISUAL_TOOL.md` |
| API documentation | `docs/functions/` | `docs/functions/BACKEND_API.md` |
| Development guides | `docs/` | `docs/DEVELOPMENT_GUIDE.md` |
| Code examples | `docs/examples/` | `docs/examples/api_usage.md` |

---

## 🔧 Automated Cleanup Script (Future)

### Proposed Script: `cleanup_docs.sh`

```bash
#!/bin/bash
# cleanup_docs.sh - Find potential duplicate documentation

echo "🔍 Scanning for documentation files..."

# Find all .md files
find . -name "*.md" -type f > /tmp/md_files.txt

# Check for common duplicates
echo "📋 Checking for common duplicate patterns..."

# Check for files at root that should be in docs/
for file in $(find . -maxdepth 1 -name "*.md" -type f); do
    basename=$(basename "$file")
    if [ "$basename" != "README.md" ] && 
       [ "$basename" != "QUICK_START.md" ] && 
       [ "$basename" != "CHANGELOG.md" ] &&
       [ "$basename" != "CONTRIBUTING.md" ] &&
       [ "$basename" != "LICENSE.md" ]; then
        echo "⚠️  $basename should probably be in docs/ folder"
    fi
done

# Check for draft files
echo "📝 Checking for draft/temporary files..."
find . -name "DRAFT_*.md" -o -name "WIP_*.md" -o -name "TODO_*.md"

echo "✅ Scan complete!"
```

---

## 📊 Current Status

### Files Analyzed
- ✅ Root level: 2 files (README, QUICK_START)
- ✅ docs/ folder: 9 files (including FILE_MANAGEMENT.md and CLEANUP_COMPLETE.md)
- ✅ docs/functions/: 5 files
- **Total**: 16 markdown files

### Cleanup Actions Completed ✅
- ✅ **Deleted**: `PROJECT_SUMMARY.md` (redundant) - **DONE**
- ✅ **Updated**: All references to deleted file
- ✅ **Verified**: No broken links
- ✅ **Created**: FILE_MANAGEMENT.md guide
- ✅ **Created**: CLEANUP_COMPLETE.md summary

### Current Structure (After Cleanup)
- **Root level**: 2 files (README, QUICK_START) ✅
- **docs/ folder**: 9 files ✅
- **docs/functions/**: 5 files ✅
- **Total**: 16 markdown files ✅
- **Status**: Clean and organized! 🎉

See [CLEANUP_COMPLETE.md](CLEANUP_COMPLETE.md) for detailed cleanup report.

---

## ✅ Post-Cleanup Verification

After deleting files, verify:

### 1. No Broken Links
```bash
# Check all markdown files for broken links
grep -r "PROJECT_SUMMARY" . --include="*.md"
```

### 2. Git Status Clean
```bash
git status
# Should show PROJECT_SUMMARY.md as deleted
```

### 3. Documentation Still Accessible
- [ ] README.md loads correctly
- [ ] QUICK_START.md loads correctly  
- [ ] docs/README.md links work
- [ ] All function guides accessible

### 4. References Updated
- [ ] Main README doesn't reference deleted file
- [ ] docs/README.md doesn't reference deleted file
- [ ] No broken links in any doc

---

## 🚨 Warning Signs

### Signs of Poor Documentation Hygiene

- ❌ Multiple files with similar names (PROJECT_SUMMARY vs Project_Summary vs project-summary)
- ❌ Draft files older than 30 days
- ❌ Documentation at root that isn't user-facing
- ❌ Duplicate content across multiple files
- ❌ Outdated "TODO" sections never completed
- ❌ Version numbers in filenames (README_v2.md)

### What to Do
1. **Consolidate** similar files
2. **Delete** old drafts
3. **Move** developer docs to `docs/`
4. **Merge** duplicate content
5. **Complete** or delete TODOs
6. **Use git history** instead of version numbers in filenames

---

## 📞 Questions to Ask

Before deleting any documentation:

1. ✅ **Is this information available elsewhere?**
2. ✅ **Is the other version more current/complete?**
3. ✅ **Are there any links pointing to this file?**
4. ✅ **Is this file referenced in code comments?**
5. ✅ **Will deleting this break anything?**

If "NO" to questions 3-5 and "YES" to questions 1-2 → Safe to delete

---

## 🔄 Regular Maintenance Tasks

### Every Sprint/Month
- [ ] Review new .md files added
- [ ] Check for drafts to finalize or delete
- [ ] Update outdated documentation
- [ ] Remove deprecated guides

### Every Quarter
- [ ] Full documentation audit
- [ ] Consolidate redundant guides
- [ ] Reorganize if structure outgrown
- [ ] Update this guide if patterns change

### Every Release
- [ ] Update version-specific docs
- [ ] Archive old migration guides
- [ ] Update API documentation
- [ ] Review all links still valid

---

## 📚 Related Guides

- [Documentation Hub](README.md) - Start here for all docs
- [Project Structure](PROJECT_STRUCTURE.md) - File organization
- [Development Guide](DEVELOPMENT_GUIDE.md) - General practices

---

**Last Updated**: October 2025  
**Next Review**: November 2025

This guide should be reviewed and updated monthly to reflect current documentation practices.
