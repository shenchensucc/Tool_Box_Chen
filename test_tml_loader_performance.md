# TML Data Loader Performance Testing Guide

## Optimizations Implemented

1. ✅ **Backend Health Check Caching** - Cached for 30 seconds using `@st.cache_resource`
2. ✅ **Template Download Caching** - Cached for 5 minutes using `@st.cache_data`
3. ✅ **Workflow Selection Fragment** - Isolated using `@st.fragment` to prevent full page reloads

## Manual Testing Checklist

### Test 1: Backend Health Check Caching
**Expected Behavior:** Health check should only occur once every 30 seconds, not on every interaction.

**Steps:**
1. Start the backend server: `uv run uvicorn backend.main:app --reload`
2. Start the frontend: `streamlit run frontend/Home.py`
3. Navigate to TML Data Loader page
4. Check browser network tab (F12 → Network)
5. Interact with checkboxes/buttons multiple times within 30 seconds
6. **Expected:** Only ONE `/health` request in the first 30 seconds
7. Wait 30+ seconds and interact again
8. **Expected:** A new `/health` request appears

**Status:** ⏳ Requires manual testing

---

### Test 2: Template Download Caching
**Expected Behavior:** Templates should download once per session, then be served from cache.

**Steps:**
1. Open TML Data Loader page (fresh browser session)
2. Check browser network tab (F12 → Network)
3. Observe initial page load - should see 2 template download requests:
   - `/api/tml/download-template/source`
   - `/api/tml/download-template/tm_loader`
4. Click "Select All" button
5. Click "Deselect All" button
6. Check/uncheck individual workflow checkboxes
7. **Expected:** NO additional template download requests
8. Templates remain available for download buttons

**Status:** ⏳ Requires manual testing

---

### Test 3: Workflow Selection Fragment Performance
**Expected Behavior:** Clicking "Select All" / "Deselect All" should be near-instantaneous.

**Steps:**
1. Open TML Data Loader page
2. Click "Select All" button
3. **Expected:** All 20 checkboxes check instantly (~0.2-0.5 seconds)
4. Click "Deselect All" button
5. **Expected:** All checkboxes uncheck instantly (~0.2-0.5 seconds)
6. Manually check/uncheck individual workflow checkboxes
7. **Expected:** Each interaction is instant with no noticeable delay
8. Check browser network tab - should see minimal/no network activity

**Status:** ⏳ Requires manual testing

---

### Test 4: File Upload Performance
**Expected Behavior:** File uploads should not trigger unnecessary operations.

**Steps:**
1. Open TML Data Loader page
2. Upload a source file
3. **Expected:** Fast upload, no delays
4. Upload a template file
5. **Expected:** Fast upload, no delays
6. Change uploaded files
7. **Expected:** Processing result clears, no other side effects

**Status:** ⏳ Requires manual testing

---

### Test 5: End-to-End Processing Workflow
**Expected Behavior:** Complete workflow should function identically to before optimization.

**Steps:**
1. Upload source Excel file
2. Upload template Excel file
3. Select multiple workflows (e.g., workflows 2, 4, 5, 10)
4. Click "Process TML Data" button
5. **Expected:** Processing completes successfully
6. **Expected:** Results display correctly with workflow summary
7. Download ZIP file
8. **Expected:** ZIP contains correct Excel files
9. Download combined Excel file
10. **Expected:** Combined file contains all workflow data

**Status:** ⏳ Requires manual testing

---

### Test 6: Backend Unavailability Detection
**Expected Behavior:** Should detect backend down within 30 seconds.

**Steps:**
1. Start with backend running
2. Open TML Data Loader page (should load successfully)
3. Stop the backend server
4. Wait 30+ seconds (for cache to expire)
5. Interact with the page (click a button)
6. **Expected:** Error message appears about backend unavailability

**Status:** ⏳ Requires manual testing

---

## Performance Metrics to Observe

### Before Optimization
- **Page Load Time:** 2-3 seconds
- **Select All Click:** 2-3 seconds delay
- **Checkbox Click:** 1-2 seconds delay
- **Network Requests per Interaction:** 3+ (health check + 2 template downloads)

### After Optimization (Expected)
- **Page Load Time:** 2-3 seconds (first load only)
- **Select All Click:** 0.2-0.5 seconds
- **Checkbox Click:** 0.1-0.3 seconds
- **Network Requests per Interaction:** 0 (cached)
- **Subsequent Page Loads:** 0.5-1 second (cached data)

### Performance Improvement
- **85-90% faster** for user interactions after initial page load

---

## Browser Developer Tools Testing

### Network Tab Monitoring
1. Open DevTools (F12)
2. Go to Network tab
3. Filter by "Fetch/XHR"
4. Monitor requests during interactions:
   - Initial load: Should see health check + 2 template downloads
   - Subsequent interactions: Should see NO requests (all cached)
   - After 30s: One health check request
   - After 5 min: Template downloads refresh if buttons clicked

### Performance Tab
1. Open DevTools (F12)
2. Go to Performance tab
3. Record a session
4. Click "Select All" button
5. Stop recording
6. **Expected:** Minimal JavaScript execution time, no network delays

---

## Automated Testing Notes

The following aspects are difficult to test automatically with Streamlit:
- Cache behavior (requires session simulation)
- Fragment rendering (Streamlit internal behavior)
- Network request timing

**Recommendation:** Manual testing is required for performance validation.

---

## Rollback Plan

If issues are discovered, revert changes:

```bash
# Revert frontend_utils.py
git checkout HEAD -- frontend/frontend_utils.py

# Revert TML Data Loader page
git checkout HEAD -- frontend/pages/2_TML_Data_Loader.py
```

---

## Success Criteria

✅ All manual tests pass
✅ No functional regressions
✅ User interactions feel instant after initial load
✅ Processing workflow completes successfully
✅ Network requests reduced by 90%+ for subsequent interactions

---

## Notes for User

**To test the optimizations:**

1. **Start Backend:**
   ```bash
   uv run uvicorn backend.main:app --reload
   ```

2. **Start Frontend:**
   ```bash
   streamlit run frontend/Home.py
   ```

3. **Navigate to:** TML Data Loader page

4. **Test interactions:**
   - Click "Select All" - should be instant
   - Click "Deselect All" - should be instant
   - Check/uncheck individual workflows - should be instant
   - Upload files - should be fast
   - Process data - should work as before

5. **Monitor performance:**
   - Open browser DevTools (F12)
   - Watch Network tab for reduced requests
   - Feel the speed difference!

**Expected Experience:**
After the initial page load, all interactions should feel nearly instantaneous with no noticeable delays.

