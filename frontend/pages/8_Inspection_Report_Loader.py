import base64
import hashlib
import json
import math
import sys
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    BACKEND_URL,
    apply_custom_styling,
    check_backend_health,
    display_header,
    display_session_privacy_banner,
    display_sidebar_navigation,
    fu_key,
    get_layout_main,
    set_page_config,
    show_backend_unavailable_and_retry,
)
from chat_panel import render_floating_chat_shell

set_page_config("Inspection Report Loader", "📄")
apply_custom_styling()
display_sidebar_navigation()

main = get_layout_main()

# ── Floating PDF panel ─────────────────────────────────────────────────────────
# The panel is injected into Streamlit's parent DOM via window.parent.
# A companion <style> tag adds padding-right to the main content block so the
# panel never covers page content — it sits beside it.

_PANEL_WIDTH_VW  = 40          # percent of viewport width
_PANEL_STYLE_ID  = "insp-pdf-panel-style"
_PANEL_DATA_ATTR = "data-insp-pdf-panel"


def _insp_pdf_floating_panel_html(panel_id: str, pdfjs_base: str,
                                   pdf_list: list, init_idx: int = 0) -> str:
    """Build the floating panel HTML with browser-style tabs for all uploaded PDFs.

    pdf_list: [{"name": filename, "b64": base64_string}, ...]
    init_idx: which tab to show first
    """
    import json as _json
    pw = _PANEL_WIDTH_VW
    pdf_list_js = _json.dumps(pdf_list)
    return f"""<!DOCTYPE html>
<html><head><style>html,body{{margin:0;padding:0;background:transparent;overflow:hidden;}}</style></head>
<body><script>
(function() {{
  var pid     = {repr(panel_id)};
  var pjsBase = {repr(pdfjs_base)};
  var pdfList = {pdf_list_js};   /* [{{name, b64}}, ...] */
  var initIdx = {init_idx};
  var pw      = {pw};
  var P       = window.parent.document;

  /* ── Layout CSS — push main content left ── */
  var styleId = {repr(_PANEL_STYLE_ID)};
  if (!P.getElementById(styleId)) {{
    var st = P.createElement('style');
    st.id  = styleId;
    st.textContent =
      'div[data-testid="stMainBlockContainer"],' +
      'div[data-testid="stAppViewBlockContainer"] {{' +
      '  max-width:none !important;' +
      '  padding-right:calc(' + pw + 'vw + 28px) !important;' +
      '  box-sizing:border-box !important;' +
      '  transition:padding-right .2s ease;' +
      '}}';
    P.head.appendChild(st);
  }}

  /* ── Guard: skip if panel already exists ── */
  P.querySelectorAll('[{_PANEL_DATA_ATTR}]').forEach(function(el) {{
    if (el.id !== pid) el.remove();
  }});
  if (P.getElementById(pid)) {{
    P.getElementById(pid).style.display = '';
    return;
  }}

  /* ══════════════════ BUILD PANEL ══════════════════ */
  var panel = P.createElement('div');
  panel.id  = pid;
  panel.setAttribute('{_PANEL_DATA_ATTR}', '1');
  panel.style.cssText = [
    'position:fixed','right:0','top:58px',
    'width:' + pw + 'vw','height:calc(100vh - 58px)',
    'z-index:9000','background:#1e1e1e',
    'border-left:2px solid #3c3c3c',
    'display:flex','flex-direction:column','overflow:hidden',
    'box-shadow:-4px 0 20px rgba(0,0,0,.6)'
  ].join(';');

  /* ── Tab bar ── */
  var tabBar = P.createElement('div');
  tabBar.style.cssText = [
    'display:flex','align-items:flex-end',
    'background:#252526','border-bottom:1px solid #3c3c3c',
    'overflow-x:auto','flex-shrink:0',
    'scrollbar-width:thin','padding-top:4px'
  ].join(';');

  /* close button sits right of tabs */
  var closeBtn = P.createElement('button');
  closeBtn.style.cssText = [
    'margin-left:auto','flex-shrink:0',
    'background:transparent','border:none',
    'color:#858585','cursor:pointer',
    'font-size:18px','line-height:1',
    'padding:4px 10px','align-self:center'
  ].join(';');
  closeBtn.title = 'Dismiss';
  closeBtn.textContent = '\u00d7';

  /* ── Zoom toolbar ── */
  var zoomBar = P.createElement('div');
  zoomBar.style.cssText = [
    'padding:4px 12px','background:#2d2d2d',
    'border-bottom:1px solid #3c3c3c',
    'display:flex','align-items:center','gap:8px','flex-shrink:0',
    'cursor:move','user-select:none'
  ].join(';');
  var zpct = P.createElement('span');
  zpct.style.cssText = 'color:#ccc;min-width:42px;font:12px ui-monospace,monospace;';
  zpct.textContent = '130%';
  function mkZBtn(lbl) {{
    var b = P.createElement('button');
    b.textContent = lbl;
    b.style.cssText = 'padding:1px 9px;border-radius:4px;border:1px solid #666;background:#444;color:#fff;cursor:pointer;font-size:13px;';
    return b;
  }}
  var zOut = mkZBtn('\u2212'), zIn = mkZBtn('+'), zRst = mkZBtn('Reset');
  zRst.style.fontSize = '11px';
  zoomBar.append(
    Object.assign(P.createElement('span'), {{style:'color:#aaa;font:600 11px system-ui;', textContent:'Zoom'}}),
    zOut, zpct, zIn, zRst
  );

  /* ── Scrollable PDF area ── */
  var wrap = P.createElement('div');
  wrap.style.cssText = 'flex:1;overflow:auto;background:#3c3c3c;padding:8px;';
  var pages = P.createElement('div');
  pages.style.cssText = 'width:max-content;min-width:100%;';
  var errEl = P.createElement('div');
  errEl.style.cssText = 'display:none;color:#f88;padding:12px;font:13px system-ui;';
  wrap.append(pages, errEl);

  panel.append(tabBar, zoomBar, wrap);
  P.body.appendChild(panel);

  /* ══════════════════ STATE ══════════════════ */
  var pdfCache  = {{}};          /* idx → pdfjs document */
  var activeIdx = initIdx;
  var baseScale = 1.1, curScale = baseScale * 1.3;
  var tabEls    = [];

  /* ══════════════════ TAB CREATION ══════════════════ */
  function shortName(name) {{
    /* strip extension and truncate to 22 chars */
    var n = name.replace(/\\.pdf$/i, '');
    return n.length > 22 ? n.slice(0, 20) + '\u2026' : n;
  }}
  pdfList.forEach(function(item, idx) {{
    var tab = P.createElement('div');
    tab.title = item.name;
    tab.style.cssText = [
      'display:flex','align-items:center','gap:5px',
      'padding:5px 12px 6px','cursor:pointer',
      'border-right:1px solid #3c3c3c',
      'font:12px system-ui,sans-serif',
      'white-space:nowrap','flex-shrink:0',
      'user-select:none','min-width:0',
      'border-top:2px solid transparent',
      'transition:background .15s'
    ].join(';');
    var ico  = P.createElement('span');
    ico.textContent = '\U0001F4C4';  /* 📄 */
    var lbl  = P.createElement('span');
    lbl.textContent = shortName(item.name);
    tab.append(ico, lbl);
    tab.addEventListener('click', function() {{ switchTo(idx); }});
    tabEls.push(tab);
    tabBar.appendChild(tab);
  }});
  tabBar.appendChild(closeBtn);

  function setActiveTab(idx) {{
    tabEls.forEach(function(t, i) {{
      if (i === idx) {{
        t.style.background   = '#1e1e1e';
        t.style.color        = '#ffffff';
        t.style.borderTop    = '2px solid #007acc';
      }} else {{
        t.style.background   = '#2d2d2d';
        t.style.color        = '#969696';
        t.style.borderTop    = '2px solid transparent';
      }}
    }});
    /* scroll active tab into view */
    if (tabEls[idx]) tabEls[idx].scrollIntoView({{block:'nearest',inline:'nearest'}});
  }}

  /* ══════════════════ RENDERING ══════════════════ */
  function zPct() {{ return Math.round((curScale / baseScale) * 100); }}
  function updZ()  {{ zpct.textContent = zPct() + '%'; }}

  function renderDoc(doc, preserveScroll) {{
    var saved = (preserveScroll && wrap) ? wrap.scrollTop : 0;
    pages.innerHTML = '';
    errEl.style.display = 'none';
    var chain = Promise.resolve();
    for (var p = 1; p <= doc.numPages; p++) {{
      (function(n) {{
        chain = chain.then(function() {{
          return doc.getPage(n).then(function(page) {{
            var vp  = page.getViewport({{scale: curScale}});
            var cv  = P.createElement('canvas');
            var ctx = cv.getContext('2d');
            var dpr = window.parent.devicePixelRatio || 1;
            cv.width  = Math.floor(vp.width  * dpr);
            cv.height = Math.floor(vp.height * dpr);
            cv.style.cssText = 'display:block;margin:0 auto 10px;box-shadow:0 1px 6px rgba(0,0,0,.5);' +
                               'width:' + Math.floor(vp.width) + 'px;height:' + Math.floor(vp.height) + 'px;';
            pages.appendChild(cv);
            return page.render({{
              canvasContext: ctx, viewport: vp,
              transform: dpr !== 1 ? [dpr,0,0,dpr,0,0] : null
            }}).promise;
          }});
        }});
      }})(p);
    }}
    chain.then(function() {{ if (saved) wrap.scrollTop = saved; }});
  }}

  function loadAndShow(idx, preserveScroll) {{
    if (pdfCache[idx]) {{ renderDoc(pdfCache[idx], preserveScroll); return; }}
    var lib = window.parent.pdfjsLib;
    if (!lib) {{ errEl.style.display='block'; errEl.textContent='PDF.js not loaded'; return; }}
    lib.GlobalWorkerOptions.workerSrc = pjsBase + '/pdf.worker.min.js';
    var raw = atob(pdfList[idx].b64), bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    pages.innerHTML = '<div style="color:#aaa;padding:16px;font:13px system-ui;">Loading\u2026</div>';
    lib.getDocument({{data: bytes}}).promise.then(function(doc) {{
      pdfCache[idx] = doc;
      renderDoc(doc, false);
    }}).catch(function(e) {{
      errEl.style.display = 'block';
      errEl.textContent   = 'PDF error: ' + (e && e.message || String(e));
    }});
  }}

  function switchTo(idx) {{
    activeIdx = idx;
    setActiveTab(idx);
    loadAndShow(idx, false);
  }}

  /* ══════════════════ ZOOM ══════════════════ */
  zOut.onclick = function() {{ curScale = Math.max(baseScale*.35, curScale/1.2); updZ(); if (pdfCache[activeIdx]) renderDoc(pdfCache[activeIdx], true); }};
  zIn.onclick  = function() {{ curScale = Math.min(baseScale*12,  curScale*1.2); updZ(); if (pdfCache[activeIdx]) renderDoc(pdfCache[activeIdx], true); }};
  zRst.onclick = function() {{ curScale = baseScale*1.3; updZ(); if (pdfCache[activeIdx]) renderDoc(pdfCache[activeIdx], false); }};
  updZ();

  /* ══════════════════ DRAG-TO-RESIZE (drag zoom bar) ══════════════════ */
  var dragging = false, startX = 0, startW = 0;
  zoomBar.addEventListener('mousedown', function(e) {{
    dragging = true; startX = e.clientX; startW = panel.getBoundingClientRect().width;
    function onMove(e) {{
      if (!dragging) return;
      var newW = Math.max(280, startW - (e.clientX - startX));
      var pct  = Math.round((newW / window.parent.innerWidth) * 100);
      panel.style.width = pct + 'vw';
      var st2 = P.getElementById({repr(_PANEL_STYLE_ID)});
      if (st2) st2.textContent =
        'div[data-testid="stMainBlockContainer"],' +
        'div[data-testid="stAppViewBlockContainer"] {{' +
        'max-width:none !important;padding-right:calc(' + pct + 'vw + 28px) !important;box-sizing:border-box !important;}}';
    }}
    P.addEventListener('mousemove', onMove);
    P.addEventListener('mouseup', function() {{ dragging=false; P.removeEventListener('mousemove', onMove); }}, {{once:true}});
  }});

  /* ══════════════════ CLOSE ══════════════════ */
  closeBtn.onclick = function() {{
    panel.style.display = 'none';
    var st2 = P.getElementById({repr(_PANEL_STYLE_ID)});
    if (st2) st2.remove();
  }};

  /* ══════════════════ INITIAL LOAD ══════════════════ */
  setActiveTab(initIdx);
  var lib = window.parent.pdfjsLib;
  if (lib) {{
    loadAndShow(initIdx, false);
  }} else {{
    var s = P.createElement('script');
    s.src    = pjsBase + '/pdf.min.js';
    s.onload = function() {{ loadAndShow(initIdx, false); }};
    s.onerror = function() {{ errEl.style.display='block'; errEl.textContent='Failed to load PDF.js'; }};
    P.head.appendChild(s);
  }}
}})();
</script></body></html>"""


def _render_pdf_floating_panel(pdf_files, sel_idx: int) -> None:
    """Inject floating PDF panel with browser-style tabs into the parent DOM."""
    pdfjs_base = f"{BACKEND_URL.rstrip('/')}/static/pdfjs"

    # Build the list of {name, b64} for all PDFs and a combined fingerprint
    pdf_list = []
    fp_parts = []
    for pf in pdf_files:
        raw = pf.getvalue()
        fp  = f"{pf.name}_{len(raw)}"
        fp_parts.append(fp)
        b64_key = f"insp_b64_{fp}"
        if b64_key not in st.session_state:
            st.session_state[b64_key] = base64.b64encode(raw).decode()
        pdf_list.append({"name": pf.name, "b64": st.session_state[b64_key]})

    combined_fp = "|".join(fp_parts)
    panel_id = "insp-pdf-" + hashlib.md5(combined_fp.encode(), usedforsecurity=False).hexdigest()[:12]
    html_key = f"insp_pdf_float_{panel_id}"
    done_key = f"insp_pdf_done_{panel_id}"

    if html_key not in st.session_state:
        st.session_state[html_key] = _insp_pdf_floating_panel_html(
            panel_id, pdfjs_base, pdf_list, sel_idx
        )

    if not st.session_state.get(done_key):
        st_components.html(st.session_state[html_key], height=0, scrolling=False)
        st.session_state[done_key] = True


def _cleanup_pdf_panel() -> None:
    """Remove floating panel + layout CSS from parent DOM."""
    # Reset injection flags so panels can be re-injected after re-toggle
    for key in list(st.session_state.keys()):
        if key.startswith("insp_pdf_done_"):
            del st.session_state[key]
    st_components.html(
        f"""<script>
        var P = window.parent.document;
        P.querySelectorAll('[{_PANEL_DATA_ATTR}]').forEach(function(el){{el.remove();}});
        var st = P.getElementById({repr(_PANEL_STYLE_ID)});
        if (st) st.remove();
        </script>""",
        height=0, scrolling=False,
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _clear_insp_results():
    """Called on file-uploader change — clear stale results.
    Auto-read is scheduled only on the very first upload (no prior results).
    Subsequent adds/changes require the user to click Read Reports manually."""
    first_upload = "insp_result" not in st.session_state
    st.session_state.pop("insp_result", None)
    st.session_state.pop("insp_gen_from_table_result", None)
    st.session_state.pop("insp_result_id", None)
    st.session_state.pop("insp_df_ver", None)
    st.session_state.pop(_LIVE_EDITOR_KEY, None)
    for k in list(st.session_state.keys()):
        if k.startswith("insp_working_df_"):
            st.session_state.pop(k, None)
    if first_upload:
        st.session_state["insp_auto_read_pending"] = True


def _pdf_page_count(pdf_bytes: bytes) -> int:
    try:
        import pymupdf

        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as doc:
            return len(doc)
    except Exception:
        return 0


def _insp_edit_columns(summary: list) -> tuple[list, pd.DataFrame]:
    EDIT_COLS = ["Circuit", "CML", "Min Reading", "Date", "Equipment ID"]
    df_full = pd.DataFrame(summary)
    edit_cols = [c for c in EDIT_COLS if c in df_full.columns]
    return edit_cols, df_full[edit_cols].copy() if edit_cols else df_full.copy()


_LIVE_EDITOR_KEY = "insp_live_editor"

_EDITOR_COL_CONFIG = {
    "Circuit":      st.column_config.TextColumn("Circuit",            width="medium"),
    "CML":          st.column_config.TextColumn("CML",                width="small"),
    "Min Reading":  st.column_config.NumberColumn("Min Reading (in)", format="%.4f", width="small"),
    "Date":         st.column_config.TextColumn("Date (YYYY-MM-DD)", width="medium"),
    "Equipment ID": st.column_config.TextColumn("Equipment ID",       width="large"),
}


def _show_live_extracted_table(slot, summary: list, *, caption: str) -> None:
    """Editable live table during multi-file reading.
    Uses a stable key so user edits survive between partial updates.
    The final fragment reads st.session_state[_LIVE_EDITOR_KEY] to carry edits forward."""
    if not summary:
        slot.empty()
        return

    _, df_new = _insp_edit_columns(summary)

    # Merge: keep user edits from the previous partial table for rows that already existed.
    prev = st.session_state.get(_LIVE_EDITOR_KEY)
    if isinstance(prev, pd.DataFrame) and not prev.empty and set(prev.columns) == set(df_new.columns):
        n_prev = len(prev)
        if n_prev <= len(df_new):
            # Preserve user edits for already-visible rows; append new rows at the bottom.
            merged = df_new.copy()
            merged.iloc[:n_prev] = prev.values
            df_new = merged

    with slot.container():
        st.caption(caption)
        st.data_editor(
            df_new,
            use_container_width=True,
            num_rows="dynamic",
            key=_LIVE_EDITOR_KEY,
            column_config=_EDITOR_COL_CONFIG,
        )


def _do_read(
    pdf_files,
    status_slots: list,
    table_ph,
) -> None:
    """Per-file progress bars (polling every 2 s); time-estimate fills bar between completions."""
    import concurrent.futures
    import time
    import traceback as _tb

    url = f"{BACKEND_URL}/api/tml/inspection-report/read"
    n_files = len(pdf_files)

    # Count pages once (fast, ~50 ms) for time estimation
    page_counts = [_pdf_page_count(pf.getvalue()) for pf in pdf_files]

    def _estimate_secs(pages: int) -> float:
        # Conservative OCR estimate: ~8 s/page + 6 s overhead.
        # Text-based PDFs finish much faster and the bar just jumps to 100 %.
        return max(14.0, 6.0 + max(pages, 1) * 8.0)

    # Initialise per-file progress bars at 0 %
    for i, pf in enumerate(pdf_files):
        pages = page_counts[i]
        pg_str = f" ({pages} pages)" if pages else ""
        status_slots[i].progress(0.0, text=f"⏳ **{pf.name}**{pg_str}")

    def _read_one(idx: int, pf):
        data = pf.getvalue()
        files_payload = [("pdf_files", (pf.name, data, "application/pdf"))]
        with httpx.Client(timeout=360.0) as client:
            resp = client.post(url, files=files_payload)
        return idx, pf.name, resp

    per_file_results: dict = {}
    per_file_errors: dict = {}
    files_finished = 0

    try:
        max_w = min(n_files, 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
            future_map = {pool.submit(_read_one, i, pf): i for i, pf in enumerate(pdf_files)}
            # Record start time per file index
            start_times: dict = {idx: time.time() for idx in future_map.values()}

            pending = set(future_map.keys())
            while pending:
                now = time.time()
                done_set, pending = concurrent.futures.wait(pending, timeout=2.0)

                # --- update in-flight bars with time-based estimate ---
                for fut in pending:
                    idx = future_map[fut]
                    elapsed = now - start_times[idx]
                    est = _estimate_secs(page_counts[idx])
                    pct = min(0.93, elapsed / est)
                    pf = pdf_files[idx]
                    status_slots[idx].progress(
                        pct,
                        text=f"⏳ **{pf.name}** — {int(elapsed)}s elapsed",
                    )

                # --- process newly-completed futures ---
                for fut in done_set:
                    orig_idx = future_map[fut]
                    try:
                        idx, name, resp = fut.result()
                        files_finished += 1

                        if resp.status_code == 200:
                            data = resp.json()
                            n_cml = len(data.get("summary", []))
                            elapsed_done = time.time() - start_times[idx]
                            status_slots[idx].progress(
                                1.0,
                                text=f"✅ **{name}** — {n_cml} CML(s) found ({int(elapsed_done)}s)",
                            )
                            per_file_results[idx] = data

                            # Live preview table when multiple files
                            if n_files > 1:
                                partial: list = []
                                for j in sorted(per_file_results.keys()):
                                    partial.extend(per_file_results[j].get("summary", []))
                                if partial:
                                    _show_live_extracted_table(
                                        table_ph,
                                        partial,
                                        caption=(
                                            f"📋 **{len(partial)} CML(s)** from "
                                            f"{files_finished}/{n_files} files — edit now or wait for all"
                                        ),
                                    )
                        else:
                            status_slots[orig_idx].progress(
                                1.0,
                                text=f"❌ **{pdf_files[orig_idx].name}** — read failed (HTTP {resp.status_code})",
                            )
                            per_file_errors[orig_idx] = _format_error(resp, f"{pdf_files[orig_idx].name} failed")
                    except httpx.TimeoutException:
                        files_finished += 1
                        status_slots[orig_idx].progress(1.0, text=f"❌ **{pdf_files[orig_idx].name}** — timed out")
                        per_file_errors[orig_idx] = "Request timed out. Try fewer or smaller PDFs."
                    except httpx.ConnectError:
                        files_finished += 1
                        status_slots[orig_idx].progress(1.0, text=f"❌ **{pdf_files[orig_idx].name}** — connection error")
                        per_file_errors[orig_idx] = f"Could not connect to backend at `{BACKEND_URL}`."
                    except Exception as exc:
                        files_finished += 1
                        status_slots[orig_idx].progress(1.0, text=f"❌ **{pdf_files[orig_idx].name}** — error")
                        per_file_errors[orig_idx] = f"{type(exc).__name__}: {exc}\n\n```\n{_tb.format_exc()}\n```"


    except Exception as exc:
        st.session_state.insp_read_error = f"{type(exc).__name__}: {exc}\n\n```\n{_tb.format_exc()}\n```"
        return

    if per_file_errors and not per_file_results:
        st.session_state.insp_read_error = per_file_errors[min(per_file_errors.keys())]
        return

    merged_summary: list = []
    for idx in sorted(per_file_results.keys()):
        merged_summary.extend(per_file_results[idx].get("summary", []))

    st.session_state.insp_result = {"success": True, "summary": merged_summary}
    st.session_state.pop("insp_gen_from_table_result", None)


def _format_error(response: httpx.Response, context: str) -> str:
    parts = [
        f"**{context}**",
        f"- URL: `{response.url}`",
        f"- Status: {response.status_code} {response.reason_phrase}",
    ]
    try:
        body = response.json()
        if isinstance(body, dict) and "detail" in body:
            d = body["detail"]
            if isinstance(d, list):
                parts.append("- Detail (validation errors):")
                for item in d[:5]:
                    parts.append(f"  • {item}")
            else:
                parts.append(f"- Detail: {d}")
        else:
            parts.append(f"- Response: {str(body)[:500]}")
    except Exception:
        text = response.text[:500] if response.text else "(empty)"
        parts.append(f"- Body: {text}")
    if response.status_code == 404:
        parts.append("\n💡 **Tip:** Restart the backend server if you added new endpoints.")
    return "\n".join(parts)


def _sanitize_rows_for_json(df: pd.DataFrame) -> list:
    raw = df.to_dict(orient="records")
    return [
        {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in row.items()}
        for row in raw
    ]


@st.fragment
def _render_results_section() -> None:
    """Step 3 runs as a fragment — table edits rerun only this section, not the whole page."""
    if "insp_result" not in st.session_state:
        st.caption("Output will appear here after processing.")
        return

    res     = st.session_state.insp_result
    success = res.get("success", False)
    summary = res.get("summary", [])

    if success and summary:
        st.success(
            f"✅ Read **{len(summary)}** CML(s). "
            "Edit the table below, then click **Generate Dataloader from Table**."
        )

        result_id = hashlib.md5(
            json.dumps(summary, sort_keys=True, default=str).encode(),
            usedforsecurity=False,
        ).hexdigest()[:14]
        buf_key = f"insp_working_df_{result_id}"

        if st.session_state.get("insp_result_id") != result_id:
            st.session_state["insp_result_id"] = result_id
            st.session_state["insp_df_ver"] = 0
            _, df_seed = _insp_edit_columns(summary)

            # Carry forward any edits the user made in the live preview table.
            # The live editor (stable key) holds their last cumulative edits.
            live = st.session_state.get(_LIVE_EDITOR_KEY)
            if (
                isinstance(live, pd.DataFrame)
                and not live.empty
                and set(live.columns) == set(df_seed.columns)
            ):
                if len(live) >= len(df_seed):
                    # User may have added rows — keep all of them
                    st.session_state[buf_key] = live.copy()
                else:
                    # Append extra rows from the full result that weren't yet visible
                    extra = df_seed.iloc[len(live):]
                    st.session_state[buf_key] = pd.concat([live, extra], ignore_index=True)
            else:
                st.session_state[buf_key] = df_seed

            # Done with live editor state — clean up
            st.session_state.pop(_LIVE_EDITOR_KEY, None)

        st.markdown("##### Extracted Readings")

        # ── Insert-row controls (compact row above the table) ──────────────────
        # Keep a version counter so bumping it changes editor_key → data_editor
        # re-initialises from the new buf_key that contains the inserted row.
        ver = int(st.session_state.get("insp_df_ver", 0))
        cur = st.session_state[buf_key]
        n_rows = len(cur)

        ins_c1, ins_c2, ins_c3 = st.columns([3, 1, 4])
        with ins_c1:
            ins_before = st.number_input(
                "Insert blank row before row #",
                min_value=1,
                max_value=n_rows + 1,
                value=1,
                key=f"insp_ins_pos_{result_id}",
                label_visibility="collapsed",
                help="Row number to insert before (1 = very top, last = append at end).",
            )
        with ins_c2:
            ins_btn = st.button(
                "＋ Insert",
                key=f"insp_ins_btn_{result_id}",
                help=f"Insert a blank row before row {ins_before}.",
                use_container_width=True,
            )
        with ins_c3:
            st.caption(
                f"↑ Insert blank row at a position (1–{n_rows + 1}). "
                "Use the **＋** at the table bottom to append."
            )

        # ── Data editor ────────────────────────────────────────────────────────
        # KEY FIX (Streamlit issue #7749): pass the stable buf_key base and do NOT
        # write edited_df back to buf_key on normal reruns.  The data_editor tracks
        # user edits internally via editor_key.  Only update buf_key on Insert so
        # the new row is included in the next re-initialisation.
        editor_key = f"insp_data_editor_{result_id}_v{ver}"
        edited_df = st.data_editor(
            st.session_state[buf_key],   # stable base — never overwritten during normal editing
            use_container_width=True,
            num_rows="dynamic",
            key=editor_key,
            column_config=_EDITOR_COL_CONFIG,
        )

        if ins_btn:
            # Capture the current editor state (includes user cell-edits) as the new base,
            # inject the blank row at the chosen position, bump version → fresh editor.
            idx = min(max(int(ins_before) - 1, 0), len(edited_df))
            empty_row = pd.DataFrame([{c: None for c in edited_df.columns}])
            new_base = pd.concat(
                [edited_df.iloc[:idx], empty_row, edited_df.iloc[idx:]],
                ignore_index=True,
            )
            st.session_state[buf_key] = new_base
            st.session_state["insp_df_ver"] = ver + 1
            try:
                st.rerun(scope="fragment")
            except TypeError:
                st.rerun()

        gen_from_table_btn = st.button(
            "📊 Generate Dataloader from Table",
            type="primary",
            use_container_width=True,
            key="insp_gen_from_table",
            help="Build APM dataloader Excel from the edited table above.",
        )

        if gen_from_table_btn:
            # Use edited_df (data_editor return value) — it contains all user edits
            # including any made during this fragment run, even without an explicit sync.
            rows_payload = _sanitize_rows_for_json(edited_df)
            with st.spinner("⏳ Building dataloader from table…"):
                try:
                    url = f"{BACKEND_URL}/api/tml/inspection-report/generate-from-table"
                    with httpx.Client(timeout=60.0) as client:
                        response = client.post(
                            url,
                            json={"rows": rows_payload, "cmms_system": "P1R-100"},
                        )
                    if response.status_code == 200:
                        st.session_state.insp_gen_from_table_result = response.json()
                    else:
                        st.error(f"❌ Generate from Table failed (HTTP {response.status_code})")
                        with st.expander("🔍 Error details", expanded=True):
                            st.markdown(_format_error(response, "Generate from Table failed"))
                except Exception as e:
                    import traceback
                    st.error(f"❌ {type(e).__name__}: {str(e)}")
                    with st.expander("🔍 Full traceback", expanded=True):
                        st.code(traceback.format_exc())

        # Download: from-table result
        gen_res = st.session_state.get("insp_gen_from_table_result")
        if gen_res and gen_res.get("download_token") and gen_res.get("records_count", 0) > 0:
            st.success(f"✅ {gen_res.get('message', '')}")
            try:
                dl = httpx.get(
                    f"{BACKEND_URL}/api/tml/download/{gen_res['download_token']}",
                    timeout=60.0,
                )
                if dl.status_code == 200:
                    st.download_button(
                        label=f"📥 Download {gen_res.get('output_filename', 'Inspection_Report_Dataloader.xlsx')}",
                        data=dl.content,
                        file_name=gen_res.get("output_filename", "Inspection_Report_Dataloader.xlsx"),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        key="insp_gen_from_table_download",
                    )
            except Exception:
                st.warning("⚠️ Could not fetch generated file. Try again.")


    elif success and res.get("records_count", 0) == 0:
        st.warning("⚠️ No records extracted. Check PDF format.")
    else:
        st.warning(res.get("message", res.get("error", "Processing completed with issues.")))


# ── Page ───────────────────────────────────────────────────────────────────────

with main:
    display_header(
        "📄 Inspection Report Loader",
        "Upload UT inspection report PDFs to read summaries or generate APM dataloader",
    )

    if not check_backend_health():
        show_backend_unavailable_and_retry()
        st.stop()

    display_session_privacy_banner()
    st.markdown("### 📋 Process Flow")

    # ── Step 1: Upload ─────────────────────────────────────────────────────────
    # Lock the uploaders only while a read is actively in progress.
    _uploading_locked = st.session_state.get("insp_reading", False)
    st.markdown("**Step 1 — Upload Inspection Report PDFs**")
    pdf_files = st.file_uploader(
        "UT Inspection Report PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="One or more UT thickness inspection report PDFs (e.g. Acuren format)",
        key=fu_key("insp", "pdfs"),
        on_change=_clear_insp_results,
        disabled=_uploading_locked,
    )

    with st.expander("📎 Optional: Source Excel (Circuit → Equipment ID)", expanded=False):
        st.caption(
            "If provided, Equipment IDs are mapped from this file. "
            "Without it, Equipment ID = 'Need Add Equipment ID' — edit in the table or in Excel before APM upload."
        )
        source_file = st.file_uploader(
            "Source Excel File",
            type=["xlsx", "xls"],
            help="Sheet 'Source_Data' with Circuit ID and Equipment ID columns",
            key=fu_key("insp", "source"),
            on_change=_clear_insp_results,
            disabled=_uploading_locked,
        )

    # ── PDF panel toggle ───────────────────────────────────────────────────────
    # Panel is injected BEFORE any spinner so it stays alive during backend reads.
    # File selection is handled by the in-panel tab bar — no Streamlit selectbox needed.
    if pdf_files:
        col_tog, _ = st.columns([2, 5])
        with col_tog:
            panel_on = st.toggle(
                "📄 PDF Preview",
                value=st.session_state.get("insp_pdf_panel_visible", True),
                key="insp_pdf_panel_toggle",
                help="Show/hide the side PDF preview panel",
            )
            st.session_state.insp_pdf_panel_visible = panel_on

        if panel_on:
            _render_pdf_floating_panel(pdf_files, sel_idx=0)
        else:
            _cleanup_pdf_panel()

    # ── Step 2: Read ───────────────────────────────────────────────────────────
    st.markdown("**Step 2 — Read Reports**")
    _is_reading  = st.session_state.get("insp_reading", False)
    _auto_read   = bool(pdf_files and st.session_state.pop("insp_auto_read_pending", False))
    _btn_busy    = _is_reading or (_auto_read and not _is_reading)

    col_read, _ = st.columns([2, 5])
    with col_read:
        read_btn = st.button(
            "⏳ Reading…" if _btn_busy else "📖 Read Reports",
            type="primary",
            disabled=not pdf_files or _btn_busy,
            key="insp_read",
            use_container_width=True,
            help="Parse the uploaded PDFs and refresh the table below.",
        )

    # Per-file status bars sit above Step 3; live table slot is under the heading
    status_host = st.empty()
    st.markdown("**Step 3 — Review, Edit & Generate Dataloader**")
    table_ph = st.empty()

    if (read_btn or _auto_read) and pdf_files and not _is_reading:
        # Clear previous results so the new read is always fresh
        st.session_state.pop("insp_result", None)
        st.session_state.pop("insp_gen_from_table_result", None)
        st.session_state.pop("insp_result_id", None)
        st.session_state.pop("insp_df_ver", None)
        st.session_state.pop(_LIVE_EDITOR_KEY, None)
        for _k in list(st.session_state.keys()):
            if _k.startswith("insp_working_df_"):
                st.session_state.pop(_k, None)
        st.session_state.insp_reading = True
        status_slots: list = []
        with status_host.container():
            status_slots = [st.empty() for _ in pdf_files]
        try:
            _do_read(pdf_files, status_slots, table_ph)
        finally:
            st.session_state.insp_reading = False
            table_ph.empty()
            status_host.empty()
        if "insp_read_error" in st.session_state:
            err = st.session_state.pop("insp_read_error")
            st.error(f"❌ {err}")

    _render_results_section()

    st.divider()
    with st.expander("ℹ️ Help & OCR"):
        st.markdown("""
        ### How It Works

        1. **Auto-read**: Reports are parsed automatically when you upload PDFs.
           Click **📖 Read Reports** to re-parse after changing files.
        2. **Generate Dataloader**: parse + produce APM dataloader Excel in one step.
        3. **Edit table**: correct OCR errors or fill Equipment IDs directly in the grid,
           then click **Generate Dataloader from Table**.
        4. **PDF panel**: fixed to the right edge, 40 % wide — content shifts left, nothing is covered.
           Drag the header to resize. Use × to dismiss; toggle the **📄 PDF Preview** switch to re-open.

        ### OCR notes
        pdfplumber runs first (fast, text-based PDFs). OCR kicks in only when pdfplumber finds no data.
        Set `INSPECTION_REPORT_IMAGE_FIRST=1` to force OCR-first for scanned/image PDFs.
        """)

    st.caption("Inspection Report Loader | Chen's Engineer Toolbox")

render_floating_chat_shell()
