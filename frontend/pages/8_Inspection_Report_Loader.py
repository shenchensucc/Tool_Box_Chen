import base64
import hashlib
import json
import math
import os
import sys
import tempfile
import traceback as _tb
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as st_components

_FRONTEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_FRONTEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from frontend_utils import (
    BACKEND_URL,
    _st_html,
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


@st.cache_data(show_spinner=False, max_entries=64)
def _cached_parse_pdf(pdf_bytes: bytes, filename: str) -> dict:
    """Parse one PDF and return a JSON-serializable result dict.

    Decorated with @st.cache_data so that the same PDF bytes (same content hash)
    are never re-parsed within a Streamlit session — Streamlit reruns triggered by
    table edits or widget interactions skip this entirely and return the cached result.

    max_entries=64: limits memory use; evicts LRU when exceeded.
    """
    from backend.tml.inspection_dataloader import generate_measurements_dataloader
    from backend.tml.inspection_report_parser import parse_inspection_report_pdf

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as f:
            f.write(pdf_bytes)
            tmp_path = Path(f.name)
        readings = parse_inspection_report_pdf(tmp_path, filename)
        if not readings:
            return {
                "success": False,
                "message": "No data extracted from PDFs.",
                "summary": [],
                "records_count": 0,
                "error": "No Circuit, CML, or readings found in uploaded PDFs.",
            }
        records_count, summary = generate_measurements_dataloader(
            readings,
            circuit_to_equipment={},
            output_path="",
            use_placeholder_when_missing=True,
        )
        return {
            "success": True,
            "message": f"Read PDF(s), extracted **{len(summary)}** row(s).",
            "records_count": records_count,
            "summary": summary,
        }
    except Exception as exc:
        import traceback as _tb2
        return {
            "success": False,
            "message": str(exc),
            "summary": [],
            "records_count": 0,
            "error": f"{type(exc).__name__}: {exc}\n\n```\n{_tb2.format_exc()}\n```",
        }
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


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
# Bump when `_insp_pdf_floating_panel_html` script changes (invalidates session cache).
_PANEL_HTML_VER  = 3


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
  var pgInfo = P.createElement('span');
  pgInfo.style.cssText = 'color:#888;font:11px system-ui;margin-left:auto;white-space:nowrap;';
  pgInfo.textContent = '';
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
    zOut, zpct, zIn, zRst, pgInfo
  );

  /* ── Brighter scrollbar CSS for the PDF wrap area ── */
  (function() {{
    var sbId = pid + '-sb';
    if (!P.getElementById(sbId)) {{
      var sbStyle = P.createElement('style');
      sbStyle.id = sbId;
      sbStyle.textContent =
        '#' + pid + ' div[style*="overflow:auto"]::-webkit-scrollbar {{' +
        '  width:10px;height:10px;}}' +
        '#' + pid + ' div[style*="overflow:auto"]::-webkit-scrollbar-track {{' +
        '  background:#1e1e1e;}}' +
        '#' + pid + ' div[style*="overflow:auto"]::-webkit-scrollbar-thumb {{' +
        '  background:#6b7280;border-radius:5px;border:2px solid #1e1e1e;}}' +
        '#' + pid + ' div[style*="overflow:auto"]::-webkit-scrollbar-thumb:hover {{' +
        '  background:#9ca3af;}}' +
        /* tab bar scrollbar */
        '#' + pid + ' div[style*="overflow-x:auto"]::-webkit-scrollbar {{' +
        '  height:4px;}}' +
        '#' + pid + ' div[style*="overflow-x:auto"]::-webkit-scrollbar-thumb {{' +
        '  background:#6b7280;border-radius:2px;}}';
      P.head.appendChild(sbStyle);
    }}
  }})();

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

  function updatePgInfo(doc) {{
    var n = doc ? doc.numPages : 0;
    pgInfo.textContent = n ? (n === 1 ? '1 page' : n + ' pages') : '';
  }}

  function loadAndShow(idx, preserveScroll) {{
    if (pdfCache[idx]) {{ renderDoc(pdfCache[idx], preserveScroll); updatePgInfo(pdfCache[idx]); return; }}
    var lib = window.parent.pdfjsLib;
    if (!lib) {{ errEl.style.display='block'; errEl.textContent='PDF.js not loaded'; return; }}
    lib.GlobalWorkerOptions.workerSrc = pjsBase + '/pdf.worker.min.js';
    var raw = atob(pdfList[idx].b64), bytes = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
    pages.innerHTML = '<div style="color:#aaa;padding:16px;font:13px system-ui;">Loading\u2026</div>';
    pgInfo.textContent = '';
    lib.getDocument({{data: bytes}}).promise.then(function(doc) {{
      pdfCache[idx] = doc;
      updatePgInfo(doc);
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

  /* ══════════════════ DRAG-TO-RESIZE (zoom bar + PDF area left edge) ══════════════════ */
  var RESIZE_EDGE_PX = 14;
  function beginPanelResize(e) {{
    if (e.button !== 0) return;
    e.preventDefault();
    var startX = e.clientX, startW = panel.getBoundingClientRect().width;
    function onMove(ev) {{
      var newW = Math.max(280, startW - (ev.clientX - startX));
      var pct  = Math.round((newW / window.parent.innerWidth) * 100);
      panel.style.width = pct + 'vw';
      var st2 = P.getElementById({repr(_PANEL_STYLE_ID)});
      if (st2) st2.textContent =
        'div[data-testid="stMainBlockContainer"],' +
        'div[data-testid="stAppViewBlockContainer"] {{' +
        'max-width:none !important;padding-right:calc(' + pct + 'vw + 28px) !important;box-sizing:border-box !important;}}';
    }}
    function onUp() {{
      P.removeEventListener('mousemove', onMove);
      P.removeEventListener('mouseup', onUp);
      wrap.style.cursor = '';
    }}
    P.addEventListener('mousemove', onMove);
    P.addEventListener('mouseup', onUp);
  }}
  zoomBar.addEventListener('mousedown', function(e) {{
    if (e.target.closest && e.target.closest('button')) return;
    beginPanelResize(e);
  }});
  wrap.addEventListener('mousedown', function(e) {{
    var pl = panel.getBoundingClientRect().left;
    if (e.clientX - pl > RESIZE_EDGE_PX) return;
    beginPanelResize(e);
  }});
  wrap.addEventListener('mousemove', function(e) {{
    var pl = panel.getBoundingClientRect().left;
    wrap.style.cursor = (e.clientX - pl <= RESIZE_EDGE_PX) ? 'ew-resize' : '';
  }});
  wrap.addEventListener('mouseleave', function() {{ wrap.style.cursor = ''; }});

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

  /* ══════════════════ AUTO-REMOVE ON PAGE NAVIGATION ══════════════════ */
  /* When Streamlit navigates away from this page it removes the component
     iframe from the DOM. Watch for that and tear down the panel + style. */
  (function() {{
    var frame = window.frameElement;
    if (!frame) return;
    new MutationObserver(function(_, obs) {{
      if (P.body.contains(frame)) return;
      obs.disconnect();
      var panelEl = P.getElementById(pid);
      if (panelEl) panelEl.remove();
      var stEl = P.getElementById(styleId);
      if (stEl) stEl.remove();
    }}).observe(P.body, {{ childList: true, subtree: true }});
  }})();
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
    html_key = f"insp_pdf_float_{panel_id}_v{_PANEL_HTML_VER}"

    if html_key not in st.session_state:
        st.session_state[html_key] = _insp_pdf_floating_panel_html(
            panel_id, pdfjs_base, pdf_list, sel_idx
        )

    # Always render so Streamlit keeps the iframe in its component tree across rerenders.
    # Same content → Streamlit reuses the iframe without re-executing the script.
    # Changed content (file set changed) → Streamlit updates the iframe → script runs →
    # removes old panel and creates new one (JS guard at top of script handles deduplication).
    st_components.html(st.session_state[html_key], height=0, scrolling=False)


def _cleanup_pdf_panel() -> None:
    """Remove floating panel + layout CSS from parent DOM."""
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
    """Called on file-uploader change — clear stale results and schedule auto-read.

    Always schedules auto-read so new/changed files are read without requiring
    a manual button click.
    """
    st.session_state.pop("insp_result", None)
    st.session_state.pop("insp_gen_from_table_result", None)
    st.session_state.pop("insp_result_id", None)
    st.session_state.pop("insp_df_ver", None)
    st.session_state.pop(_LIVE_EDITOR_KEY, None)
    for k in list(st.session_state.keys()):
        if k.startswith("insp_working_df_"):
            st.session_state.pop(k, None)
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
    "Min Reading":  st.column_config.NumberColumn("Min Reading (in)", format="%.3f", width="small"),
    "Date":         st.column_config.TextColumn("Date (YYYY-MM-DD)", width="medium"),
    "Equipment ID": st.column_config.TextColumn("Equipment ID",       width="large"),
}

# First *data* column after Streamlit’s row-selection checkboxes (we cannot merge into those cells).
# Header + default cell value use fullwidth plus (＋) as the “operations” affordance.
_INSP_ACTION_COL = "＋"
_INSP_ACTION_IDLE = "＋"
_INSP_ACTION_OPTIONS = (
    _INSP_ACTION_IDLE,
    "Insert above",
    "Insert below",
    "Delete row",
)
_INSP_ACTION_COMMANDS = frozenset({"Insert above", "Insert below", "Delete row"})

_RESULT_EDITOR_COL_CONFIG = {
    _INSP_ACTION_COL: st.column_config.SelectboxColumn(
        None,
        help="Row operations: **single-click** the cell to open the menu (insert above/below or delete). Default **＋** means no action.",
        options=list(_INSP_ACTION_OPTIONS),
        width=52,
        pinned=True,
        default=_INSP_ACTION_IDLE,
        required=False,
    ),
    **_EDITOR_COL_CONFIG,
}


def _inject_insp_action_column_style() -> None:
    """Narrow the action lane, match checkbox column background, and single-click → open ＋ cell editor."""
    css = """
    <style>
    /* Columns 1–2: row checkbox + action (＋) — same lane styling */
    div[data-testid="stDataFrame"] [role="row"] > [role="gridcell"]:nth-child(1),
    div[data-testid="stDataFrame"] [role="row"] > [role="gridcell"]:nth-child(2),
    div[data-testid="stDataFrame"] [role="row"] > [role="columnheader"]:nth-child(1),
    div[data-testid="stDataFrame"] [role="row"] > [role="columnheader"]:nth-child(2),
    div[data-testid="stDataEditor"] [role="row"] > [role="gridcell"]:nth-child(1),
    div[data-testid="stDataEditor"] [role="row"] > [role="gridcell"]:nth-child(2),
    div[data-testid="stDataEditor"] [role="row"] > [role="columnheader"]:nth-child(1),
    div[data-testid="stDataEditor"] [role="row"] > [role="columnheader"]:nth-child(2) {
        min-width: 48px !important;
        max-width: 72px !important;
        background-color: rgba(0, 0, 0, 0.03) !important;
    }
    html[data-toolbox-theme="dark"] div[data-testid="stDataFrame"] [role="row"] > [role="gridcell"]:nth-child(1),
    html[data-toolbox-theme="dark"] div[data-testid="stDataFrame"] [role="row"] > [role="gridcell"]:nth-child(2),
    html[data-toolbox-theme="dark"] div[data-testid="stDataFrame"] [role="row"] > [role="columnheader"]:nth-child(1),
    html[data-toolbox-theme="dark"] div[data-testid="stDataFrame"] [role="row"] > [role="columnheader"]:nth-child(2),
    html[data-toolbox-theme="dark"] div[data-testid="stDataEditor"] [role="row"] > [role="gridcell"]:nth-child(1),
    html[data-toolbox-theme="dark"] div[data-testid="stDataEditor"] [role="row"] > [role="gridcell"]:nth-child(2),
    html[data-toolbox-theme="dark"] div[data-testid="stDataEditor"] [role="row"] > [role="columnheader"]:nth-child(1),
    html[data-toolbox-theme="dark"] div[data-testid="stDataEditor"] [role="row"] > [role="columnheader"]:nth-child(2) {
        background-color: rgba(255, 255, 255, 0.06) !important;
    }
    </style>
    """
    # Glide Data Grid opens overlays on double-click; synthesize dblclick for the pinned ＋ column on single click.
    js = """
    <script>
    (function () {
      var MARKER = "[data-insp-plus-editor]";
      var ROW_MARKER_MAX = 58;
      var PLUS_COL_RIGHT = 128;
      var HEADER_SKIP = 42;

      function findEditorAfterMarker() {
        var m = document.querySelector(MARKER);
        if (!m) return null;
        var w = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
        var found = false;
        var node;
        while ((node = w.nextNode())) {
          if (node === m) { found = true; continue; }
          if (!found) continue;
          if (node.getAttribute && node.getAttribute("data-testid") === "stDataEditor") return node;
        }
        return null;
      }

      function install(root) {
        if (!root || root.dataset.inspPlusClickInstalled) return;
        root.dataset.inspPlusClickInstalled = "1";
        root.addEventListener(
          "click",
          function (ev) {
            var t = ev.target;
            if (!t || t.tagName !== "CANVAS") return;
            if (!root.contains(t)) return;
            var r = t.getBoundingClientRect();
            var x = ev.clientX - r.left;
            var y = ev.clientY - r.top;
            if (y < HEADER_SKIP) return;
            if (x < ROW_MARKER_MAX || x >= PLUS_COL_RIGHT) return;
            requestAnimationFrame(function () {
              t.dispatchEvent(
                new MouseEvent("dblclick", {
                  bubbles: true,
                  cancelable: true,
                  view: window,
                  detail: 2,
                  clientX: ev.clientX,
                  clientY: ev.clientY,
                  screenX: ev.screenX,
                  screenY: ev.screenY,
                  button: ev.button,
                  buttons: ev.buttons,
                })
              );
            });
          },
          true
        );
      }

      function tryInstall() {
        var ed = findEditorAfterMarker();
        if (ed) install(ed);
      }

      tryInstall();
      var obs = new MutationObserver(tryInstall);
      obs.observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """
    _st_html(css + js, allow_js=True)


def _insp_df_with_actions(buf: pd.DataFrame) -> pd.DataFrame:
    """Prepend ＋ action column immediately after the grid’s checkbox column."""
    out = buf.copy()
    out.insert(0, _INSP_ACTION_COL, [_INSP_ACTION_IDLE] * len(out))
    return out


def _insp_apply_row_action(edited: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
    """
    Apply the first real command in the ＋ column (not the default ＋ idle). Returns (data only, changed).
    """
    if edited.empty or _INSP_ACTION_COL not in edited.columns:
        return edited, False
    data_cols = [c for c in edited.columns if c != _INSP_ACTION_COL]
    if not data_cols:
        return edited, False
    for i in range(len(edited)):
        raw = edited.iloc[i][_INSP_ACTION_COL]
        if pd.isna(raw):
            continue
        act = str(raw).strip()
        if act not in _INSP_ACTION_COMMANDS:
            continue
        data = edited[data_cols].copy()
        if act == "Delete row":
            new_data = data.drop(index=i).reset_index(drop=True)
        elif act == "Insert above":
            blank = pd.DataFrame([{c: None for c in data_cols}])
            new_data = pd.concat([data.iloc[:i], blank, data.iloc[i:]], ignore_index=True)
        elif act == "Insert below":
            blank = pd.DataFrame([{c: None for c in data_cols}])
            new_data = pd.concat([data.iloc[: i + 1], blank, data.iloc[i + 1 :]], ignore_index=True)
        else:
            new_data = data
        return new_data, True
    return edited, False


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
            width="stretch",
            num_rows="dynamic",
            key=_LIVE_EDITOR_KEY,
            column_config=_EDITOR_COL_CONFIG,
        )


def _do_read(
    pdf_files,
    status_slots: list,
    table_ph,
) -> None:
    """Parse PDFs in-process. Optional HTTP fallback via env."""
    import concurrent.futures
    import time

    use_http = os.getenv("INSPECTION_REPORT_READ_VIA_HTTP", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    url = f"{BACKEND_URL}/api/tml/inspection-report/read"
    n_files = len(pdf_files)

    page_counts = [_pdf_page_count(pf.getvalue()) for pf in pdf_files]

    def _estimate_secs(pages: int) -> float:
        # Most PDFs finish via pdfplumber table parsers in 2-5 s.
        # OCR-heavy PDFs (genuinely scanned, no embedded text) take 15-30 s.
        # Use a conservative middle estimate so the bar moves smoothly either way.
        return max(5.0, 3.0 + max(pages, 1) * 2.5)

    for i, pf in enumerate(pdf_files):
        pages = page_counts[i]
        pg_str = f" ({pages} pages)" if pages else ""
        mode = "HTTP API" if use_http else "in-process"
        status_slots[i].progress(0.0, text=f"⏳ **{pf.name}**{pg_str} — {mode}")

    def _read_one_local(idx: int, pf):
        """Parse one PDF via the @st.cache_data wrapper.

        The wrapper handles temp-file lifecycle, parse, and dataloader generation.
        Calling it with the same (bytes, filename) pair hits the Streamlit cache
        and returns immediately — no re-parse on reruns or duplicate uploads.
        """
        try:
            data = _cached_parse_pdf(pf.getvalue(), pf.name)
            return idx, pf.name, data
        except Exception as exc:
            return idx, pf.name, {
                "success": False,
                "message": str(exc),
                "summary": [],
                "records_count": 0,
                "error": f"{type(exc).__name__}: {exc}\n\n```\n{_tb.format_exc()}\n```",
            }

    def _read_one_http(idx: int, pf):
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
            if use_http:
                future_map = {pool.submit(_read_one_http, i, pf): i for i, pf in enumerate(pdf_files)}
            else:
                future_map = {pool.submit(_read_one_local, i, pf): i for i, pf in enumerate(pdf_files)}

            start_times: dict = {idx: time.time() for idx in future_map.values()}

            pending = set(future_map.keys())
            while pending:
                now = time.time()
                done_set, pending = concurrent.futures.wait(pending, timeout=2.0)

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

                for fut in done_set:
                    orig_idx = future_map[fut]
                    try:
                        idx, name, payload = fut.result()
                        files_finished += 1

                        if use_http:
                            resp = payload
                            if resp.status_code == 200:
                                data = resp.json()
                                n_cml = len(data.get("summary", []))
                                elapsed_done = time.time() - start_times[idx]
                                status_slots[idx].progress(
                                    1.0,
                                    text=f"✅ **{name}** — {n_cml} row(s) ({int(elapsed_done)}s)",
                                )
                                per_file_results[idx] = data
                                if n_files > 1:
                                    partial: list = []
                                    for j in sorted(per_file_results.keys()):
                                        partial.extend(per_file_results[j].get("summary", []))
                                    if partial:
                                        _show_live_extracted_table(
                                            table_ph,
                                            partial,
                                            caption=(
                                                f"📋 **{len(partial)} row(s)** from "
                                                f"{files_finished}/{n_files} files — edit now or wait for all"
                                            ),
                                        )
                            else:
                                status_slots[orig_idx].progress(
                                    1.0,
                                    text=f"❌ **{pdf_files[orig_idx].name}** — HTTP {resp.status_code}",
                                )
                                per_file_errors[orig_idx] = _format_error(resp, f"{pdf_files[orig_idx].name} failed")
                        else:
                            data = payload
                            if data.get("success") and data.get("summary"):
                                n_cml = len(data.get("summary", []))
                                elapsed_done = time.time() - start_times[idx]
                                status_slots[idx].progress(
                                    1.0,
                                    text=f"✅ **{name}** — {n_cml} row(s) ({int(elapsed_done)}s)",
                                )
                                per_file_results[idx] = data
                                if n_files > 1:
                                    partial2: list = []
                                    for j in sorted(per_file_results.keys()):
                                        partial2.extend(per_file_results[j].get("summary", []))
                                    if partial2:
                                        _show_live_extracted_table(
                                            table_ph,
                                            partial2,
                                            caption=(
                                                f"📋 **{len(partial2)} row(s)** from "
                                                f"{files_finished}/{n_files} files — edit now or wait for all"
                                            ),
                                        )
                            else:
                                status_slots[orig_idx].progress(
                                    1.0,
                                    text=f"❌ **{name}** — parse failed",
                                )
                                per_file_errors[orig_idx] = data.get("error") or data.get("message", "Parse failed")

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


def _render_azure_di_debug_section(pdf_files) -> None:
    """Show a collapsible section with raw Azure DI OCR output per uploaded PDF.

    Useful for diagnosing missing CML zones — shows exactly what text Azure DI
    read from each page, in reading order, before any parsing logic runs.
    """
    try:
        from backend.tml.inspection_report_parser import get_azure_di_debug_data
    except ImportError:
        return

    with st.expander("Developing OCR Raw", expanded=False):
        st.caption(
            "Raw text extracted by Azure Document Intelligence before any parsing logic. "
            "Use this to diagnose missing CML zones — if a zone isn't in this output, "
            "Azure DI didn't read it from the PDF."
        )

        debug_by_name = {pf.name: get_azure_di_debug_data(pf.name) for pf in pdf_files}
        if not any(debug_by_name.values()):
            st.info("Run **Read Reports** to populate this section.")
            return

        for pf in pdf_files:
            debug = debug_by_name.get(pf.name)
            if not debug:
                st.markdown(f"**{pf.name}** — no Azure DI data (may have used local OCR fallback)")
                continue

            pages = debug.get("pages", [])
            total = debug.get("total_tokens", 0)
            st.markdown(f"**{pf.name}** — {len(pages)} page(s), {total} total tokens")

            for page_info in pages:
                pg_num = page_info.get("page", "?")
                pg_text = page_info.get("text", "")
                pg_tokens = page_info.get("token_count", 0)
                label = f"Page {pg_num}  ({pg_tokens} tokens)"
                with st.expander(label, expanded=False):
                    if pg_text:
                        st.code(pg_text, language=None)
                    else:
                        st.caption("(no text extracted from this page)")

            if len(pdf_files) > 1:
                st.divider()


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
            f"✅ Read **{len(summary)}** row(s). "
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
        st.caption(
            "**＋ column** (next to checkboxes): **single-click** the cell to open the menu and pick **Insert above**, **Insert below**, or **Delete row** "
            "(default **＋** means no action). **Toolbar:** multi-select + trash · search · download · fullscreen. "
            "**Bottom:** **＋** appends a row."
        )

        # ── Data editor ────────────────────────────────────────────────────────
        ver = int(st.session_state.get("insp_df_ver", 0))
        display_df = _insp_df_with_actions(st.session_state[buf_key])
        st.markdown(
            '<div data-insp-plus-editor="1" style="position:absolute;width:0;height:0;overflow:hidden;clip:rect(0,0,0,0);" aria-hidden="true"></div>',
            unsafe_allow_html=True,
        )
        _inject_insp_action_column_style()
        editor_key = f"insp_data_editor_{result_id}_v{ver}"
        edited_df = st.data_editor(
            display_df,
            width="stretch",
            num_rows="dynamic",
            key=editor_key,
            column_order=list(display_df.columns),
            column_config=_RESULT_EDITOR_COL_CONFIG,
        )

        new_base, did_structure = _insp_apply_row_action(edited_df)
        if did_structure:
            st.session_state[buf_key] = new_base
            st.session_state["insp_df_ver"] = ver + 1
            try:
                st.rerun(scope="fragment")
            except TypeError:
                st.rerun()
        else:
            # Toolbar row delete, bottom +, and cell edits — keep working copy in sync (no ＋ column in buf).
            st.session_state[buf_key] = edited_df.drop(
                columns=[_INSP_ACTION_COL], errors="ignore"
            ).copy()

        gen_from_table_btn = st.button(
            "📊 Generate Dataloader from Table",
            type="primary",
            width="stretch",
            key="insp_gen_from_table",
            help="Build APM dataloader Excel from the edited table above.",
        )

        if gen_from_table_btn:
            gen_df = edited_df.drop(columns=[_INSP_ACTION_COL], errors="ignore")
            rows_payload = _sanitize_rows_for_json(gen_df)
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
            width="stretch",
            help="Parse the uploaded PDFs and refresh the table below.",
        )

    # Per-file status bars sit above Step 3; live table slot is under the heading
    status_host = st.empty()
    st.markdown("**Step 3 — Review, Edit & Generate Dataloader**")
    table_ph = st.empty()

    # Manual button click: set flag + rerun so the button visually disables before blocking read starts.
    # This gives immediate UI feedback ("⏳ Reading…") instead of a frozen-looking page.
    if read_btn and pdf_files and not _is_reading and not _auto_read:
        st.session_state["insp_auto_read_pending"] = True
        st.rerun()

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
            st.session_state["insp_read_error_display"] = st.session_state.pop("insp_read_error")
        st.rerun()

    if st.session_state.get("insp_read_error_display"):
        st.error(f"❌ {st.session_state.pop('insp_read_error_display')}")

    _render_results_section()

    # ── Azure DI debug section ──────────────────────────────────────────────────
    if pdf_files:
        _render_azure_di_debug_section(pdf_files)

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

        ### Parsing
        **Read Reports** runs the PDF parser **in this Python process** (not the HTTP API), so results
        reflect your `.env` / `INSPECTION_REPORT_*` variables for Streamlit.
        Set `INSPECTION_REPORT_READ_VIA_HTTP=1` only if you need the legacy behavior (parse on the backend server).

        OCR notes: Azure Document Intelligence is used for all pages when `INSPECTION_REPORT_AZURE_DI_ONLY=1`.
        In mixed mode, pdfplumber runs first where possible; structured OCR is the fallback for image-heavy reports.
        """)

    st.caption("Inspection Report Loader | Chen's Engineer Toolbox")

render_floating_chat_shell()
