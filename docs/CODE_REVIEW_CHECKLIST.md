# 📋 Code Review Checklist

## 🎯 Purpose

This document provides a **senior-level code review framework** for ensuring consistent, high-quality code across all functions in Chen's Engineer Toolbox.

Use this checklist for **every function development**, whether AI-assisted or human-written.

---

## 🔍 Review Process Overview

```
1. Scope Verification (5 min)
   ↓
2. Architecture Review (10 min)
   ↓
3. Code Quality Review (15 min)
   ↓
4. Testing Review (10 min)
   ↓
5. Documentation Review (5 min)
   ↓
6. Security Review (10 min)
   ↓
7. Final Approval / Request Changes
```

**Estimated Time**: 45-60 minutes per feature/function

---

## 1️⃣ Scope Verification

### Critical Questions

- [ ] **Does this change match the original request?**
  - Compare PR/commit description with actual changes
  - Flag any scope creep immediately

- [ ] **Are all modified files justified?**
  - List files changed: ___________________
  - Justify each: ___________________
  - Any unjustified changes? → Request removal

- [ ] **Were AI Development Rules followed?**
  - Check against `docs/AI_DEVELOPMENT_RULES.md`
  - No unnecessary refactoring? ✓
  - No style changes outside scope? ✓
  - No "while I'm here" modifications? ✓

### Red Flags 🚩

- Changes to 5+ files for a "simple bug fix"
- Reformatted entire files
- Changes to unrelated functions
- New features not in original request
- Dependency upgrades not justified

---

## 2️⃣ Architecture Review

### System Design

- [ ] **Does this fit the existing architecture?**
  - Frontend (Streamlit) ↔ Backend (FastAPI) separation maintained?
  - No business logic in frontend?
  - No UI logic in backend?

- [ ] **Are dependencies appropriate?**
  - Check `requirements.txt` / `pyproject.toml`
  - New dependencies justified?
  - Version constraints specified?
  - No circular dependencies?

- [ ] **Is the data flow correct?**
  ```
  Frontend → API Call → Backend Endpoint → Data Processing → Response → Frontend Display
  ```
  - Each step has proper error handling?
  - Data validated at boundaries?

### Design Patterns

- [ ] **Follows established patterns in codebase?**
  - Similar endpoints use same structure?
  - Error handling consistent?
  - Response models consistent?

- [ ] **Separation of concerns?**
  - Validation in Pydantic models
  - Business logic separate from API routes
  - Utility functions properly abstracted

### Red Flags 🚩

- Frontend calling database directly (should go through API)
- Mixing async/sync code inappropriately
- Tight coupling between unrelated modules
- God objects or functions (doing too much)

---

## 3️⃣ Code Quality Review

### Readability

- [ ] **Is the code self-documenting?**
  - Variable names clear and descriptive?
  - Function names indicate purpose?
  - Magic numbers replaced with named constants?

- [ ] **Proper code organization?**
  - Related functions grouped together?
  - Logical flow (top-to-bottom readability)?
  - Functions are focused (single responsibility)?

### Python Best Practices

- [ ] **Type hints present and correct?**
  ```python
  ✅ def process_data(df: pd.DataFrame, column: str) -> pd.Series:
  ❌ def process_data(df, column):
  ```

- [ ] **Docstrings complete?**
  ```python
  ✅ def calculate_stats(series: pd.Series) -> ColumnStats:
      """
      Calculate statistical metrics for a numeric series.
      
      Args:
          series: Pandas Series with numeric values
          
      Returns:
          ColumnStats object with mean, std, min, max, quartiles
          
      Raises:
          ValueError: If series is empty or non-numeric
      """
  ```

- [ ] **Error handling appropriate?**
  - Specific exceptions caught (not bare `except:`)
  - Errors logged or returned with context
  - User-friendly error messages in API responses

- [ ] **No code smells?**
  - No duplicated code (DRY principle)
  - No dead code or commented-out blocks
  - No overly complex conditionals (max 3 levels deep)
  - No functions longer than 50 lines (guideline)

### Linting & Formatting

- [ ] **Passes all linters?**
  ```bash
  ruff check --fix .
  black .
  mypy . --ignore-missing-imports
  ```

- [ ] **Follows project style?**
  - 4-space indentation
  - Black-compatible formatting
  - Import order (standard → third-party → local)

### Red Flags 🚩

- Functions longer than 100 lines
- Nested conditionals 5+ levels deep
- Hard-coded credentials or secrets
- Mutable default arguments `def func(items=[])`
- Using `eval()` or `exec()`

---

## 4️⃣ Testing Review

### Test Coverage

- [ ] **Are new features tested?**
  - Unit tests for new functions?
  - Integration tests for new endpoints?
  - Edge cases covered?

- [ ] **Are existing tests still passing?**
  ```bash
  pytest tests/ -v
  ```
  - No broken tests?
  - No skipped tests without justification?

### Test Quality

- [ ] **Tests are meaningful?**
  ```python
  ✅ def test_preview_returns_correct_sheet_names():
      # Tests specific behavior
      
  ❌ def test_preview():
      # Too vague
  ```

- [ ] **Tests cover error cases?**
  - Invalid inputs tested?
  - Edge cases (empty data, null values)?
  - Error messages validated?

- [ ] **Tests are independent?**
  - No test interdependencies
  - Can run in any order
  - Clean state between tests

### Test Data

- [ ] **Test data is appropriate?**
  - Realistic but minimal examples
  - No sensitive/real production data
  - Test fixtures properly organized

### Red Flags 🚩

- Test coverage below 70% for new code
- Tests that always pass (not validating anything)
- Tests dependent on external services
- Commented-out tests
- Tests that modify global state

---

## 5️⃣ Documentation Review

### Code Documentation

- [ ] **All public functions documented?**
  - Docstrings with Args, Returns, Raises
  - Complex logic has inline comments
  - Non-obvious decisions explained

- [ ] **API documentation updated?**
  - FastAPI automatic docs reflect changes
  - Request/response models documented
  - Endpoint descriptions clear

### User Documentation

- [ ] **README updated if needed?**
  - New features mentioned?
  - Installation steps still accurate?
  - Examples updated?

- [ ] **Function guide updated?**
  - `docs/functions/[FUNCTION].md` updated?
  - New parameters documented?
  - Breaking changes highlighted?

### Changelog

- [ ] **Changes documented?**
  - What was changed?
  - Why it was changed?
  - Any breaking changes?
  - Migration guide if needed?

### Red Flags 🚩

- No docstrings on public functions
- Outdated examples in documentation
- Missing migration guide for breaking changes
- Documentation contradicts code behavior

---

## 6️⃣ Security Review

### Input Validation

- [ ] **All inputs validated?**
  - File uploads: type, size limits
  - API parameters: Pydantic validation
  - SQL/NoSQL queries: parameterized/safe
  - User input sanitized

- [ ] **No injection vulnerabilities?**
  - No string concatenation for queries
  - No `eval()` on user input
  - No command execution from user input

### Data Handling

- [ ] **Sensitive data protected?**
  - No passwords in code or logs
  - API keys in environment variables
  - No PII logged unnecessarily

- [ ] **File operations safe?**
  - Temporary files cleaned up
  - Path traversal prevented
  - File permissions appropriate

### API Security

- [ ] **Endpoints secured appropriately?**
  - CORS configured correctly (not `*` in production)
  - Rate limiting considered?
  - Authentication required where needed?

### Dependencies

- [ ] **Dependencies secure?**
  - No known vulnerabilities (`pip audit`)
  - Dependencies from trusted sources
  - Version pins to avoid supply chain attacks

### Red Flags 🚩

- Hardcoded secrets or passwords
- CORS `allow_origins=["*"]` in production
- No file size validation
- SQL string concatenation
- User input directly in system commands

---

## 7️⃣ Performance Review

### Efficiency

- [ ] **No obvious performance issues?**
  - Database queries optimized (N+1 queries?)
  - Large datasets handled efficiently
  - Pagination for large result sets

- [ ] **Memory usage reasonable?**
  - Large files streamed, not loaded entirely
  - Generators used for large datasets
  - Resources properly released

### Scalability Considerations

- [ ] **Will this scale?**
  - What happens with 10x data?
  - What happens with 100 concurrent users?
  - Any bottlenecks identified?

### Red Flags 🚩

- Loading entire large files into memory
- N+1 query problems
- Synchronous operations blocking async code
- No pagination on endpoints returning lists

---

## 8️⃣ Maintainability Review

### Code Organization

- [ ] **Easy to find and understand?**
  - Logical file organization
  - Related code grouped together
  - Clear module boundaries

- [ ] **Easy to modify?**
  - Low coupling between modules
  - High cohesion within modules
  - Configuration externalized

### Technical Debt

- [ ] **No new technical debt?**
  - TODOs addressed or tracked
  - Hacks explained with comments
  - Temporary solutions have removal plan

- [ ] **Existing debt not worsened?**
  - Didn't add to existing problems
  - Ideally reduced some debt

### Red Flags 🚩

- "TODO: Fix this hack" without issue tracking
- Copy-pasted code instead of abstraction
- Workarounds without explanation
- Bypassing existing abstractions

---

## ✅ Final Approval Checklist

Before approving, verify:

- [ ] All sections above reviewed
- [ ] No red flags unresolved
- [ ] Tests passing
- [ ] Linters passing
- [ ] Documentation complete
- [ ] Scope verified (no over-modification)

## 🔴 Request Changes If:

- Critical security issues found
- Major architectural concerns
- Scope significantly exceeded
- Tests failing or insufficient
- Code quality below standards

## 🟡 Approve with Comments If:

- Minor style issues (can be fixed later)
- Optional optimizations identified
- Future enhancement suggestions
- Documentation could be improved slightly

## 🟢 Approve If:

- All checklist items passed
- No blocking issues
- Good code quality
- Proper testing
- Complete documentation

---

## 📊 Review Metrics

Track these metrics over time:

- **Average time to review**: _____ minutes
- **Approval rate**: _____ %
- **Common issues found**: _____
- **Repeat violations**: _____

---

## 🎓 Reviewer Training

### Junior Reviewers Focus On:
1. Scope verification
2. Code readability
3. Test coverage
4. Documentation completeness

### Senior Reviewers Also Check:
5. Architecture alignment
6. Security implications
7. Performance considerations
8. Long-term maintainability

---

## 💡 Tips for Effective Reviews

### Do:
- ✅ Be specific in feedback
- ✅ Explain the "why" behind requests
- ✅ Suggest concrete improvements
- ✅ Acknowledge good practices
- ✅ Focus on code, not the person

### Don't:
- ❌ Nitpick style if linters pass
- ❌ Block on personal preferences
- ❌ Demand perfection over progress
- ❌ Ignore scope creep
- ❌ Skip running the code locally

---

## 🔄 Post-Review

After approval:

1. **Track decisions**: Document any important architectural decisions
2. **Update guides**: If new patterns emerge, update function guides
3. **Celebrate**: Acknowledge good work
4. **Learn**: Note any issues for future prevention

---

## 📞 Questions During Review?

- **Architecture questions**: See `docs/ARCHITECTURE.md`
- **Function-specific questions**: Check `docs/functions/[FUNCTION].md`
- **AI development questions**: Review `docs/AI_DEVELOPMENT_RULES.md`
- **Unclear requirements**: Contact the original requester

---

## 📝 Review Template

Copy this template for each review:

```markdown
## Code Review: [Feature/Function Name]

**Reviewer**: _____
**Date**: _____
**PR/Commit**: _____

### Scope Verification
- [ ] Matches original request
- [ ] All files justified
- [ ] AI rules followed (if applicable)

### Critical Issues 🔴
- None / [List issues]

### Major Concerns 🟡
- None / [List concerns]

### Minor Notes 🟢
- None / [List notes]

### Decision
- [ ] Approved
- [ ] Approved with comments
- [ ] Request changes

**Summary**: _____

**Estimated Risk**: Low / Medium / High
```

---

**Use this checklist for EVERY function development to ensure consistent quality.**

Last Updated: October 2025
