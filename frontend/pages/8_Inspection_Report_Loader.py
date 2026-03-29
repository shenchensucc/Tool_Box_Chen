import base64
import hashlib
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
    display_sidebar_navigation,
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
    """Called on file-uploader change — clear old results and request auto-read."""
    st.session_state.pop("insp_result", None)
    st.session_state.pop("insp_gen_from_table_result", None)
    st.session_state["insp_auto_read_pending"] = True


def _do_read(pdf_files) -> None:
    """Call the read endpoint once per PDF in parallel; show live per-file progress."""
    import concurrent.futures
    import traceback as _tb

    url = f"{BACKEND_URL}/api/tml/inspection-report/read"

    # Create one status slot per file — updated as each future completes
    slots = [st.empty() for _ in pdf_files]
    for i, pf in enumerate(pdf_files):
        slots[i].markdown(f"⏳ **{pf.name}** — reading…")

    def _read_one(idx: int, pf):
        data = pf.getvalue()
        files = [("pdf_files", (pf.name, data, "application/pdf"))]
        with httpx.Client(timeout=360.0) as client:
            resp = client.post(url, files=files)
        return idx, pf.name, resp

    per_file_results: dict = {}
    per_file_errors: dict  = {}

    try:
        max_w = min(len(pdf_files), 4)
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_w) as pool:
            future_map = {pool.submit(_read_one, i, pf): i for i, pf in enumerate(pdf_files)}
            for future in concurrent.futures.as_completed(future_map):
                orig_idx = future_map[future]
                try:
                    idx, name, resp = future.result()
                    if resp.status_code == 200:
                        data = resp.json()
                        n = len(data.get("summary", []))
                        slots[idx].markdown(f"✅ **{name}** — {n} CML(s) found")
                        per_file_results[idx] = data
                    else:
                        slots[orig_idx].markdown(f"❌ **{pdf_files[orig_idx].name}** — read failed")
                        per_file_errors[orig_idx] = _format_error(resp, f"{pdf_files[orig_idx].name} failed")
                except httpx.TimeoutException:
                    slots[orig_idx].markdown(f"❌ **{pdf_files[orig_idx].name}** — timed out")
                    per_file_errors[orig_idx] = "Request timed out. Try fewer or smaller PDFs."
                except httpx.ConnectError:
                    slots[orig_idx].markdown(f"❌ **{pdf_files[orig_idx].name}** — connection error")
                    per_file_errors[orig_idx] = f"Could not connect to backend at `{BACKEND_URL}`."
                except Exception as exc:
                    slots[orig_idx].markdown(f"❌ **{pdf_files[orig_idx].name}** — error")
                    per_file_errors[orig_idx] = f"{type(exc).__name__}: {exc}\n\n```\n{_tb.format_exc()}\n```"
    except Exception as exc:
        st.session_state.insp_read_error = f"{type(exc).__name__}: {exc}\n\n```\n{_tb.format_exc()}\n```"
        return

    if per_file_errors and not per_file_results:
        # All files failed — surface the first error
        st.session_state.insp_read_error = per_file_errors[min(per_file_errors.keys())]
        return

    # Merge results in original upload order
    merged_summary: list = []
    for idx in sorted(per_file_results.keys()):
        d = per_file_results[idx]
        merged_summary.extend(d.get("summary", []))

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

        EDIT_COLS = ["Circuit", "CML", "Min Reading", "Date", "Equipment ID"]
        df_full   = pd.DataFrame(summary)
        edit_cols = [c for c in EDIT_COLS if c in df_full.columns]
        df_edit   = df_full[edit_cols].copy()

        result_hash = hashlib.md5(
            str(summary[:3]).encode(), usedforsecurity=False
        ).hexdigest()[:8]

        st.markdown("##### Extracted Readings")
        st.caption(
            "✏️ Edit any cell to correct OCR errors or fill Equipment IDs. "
            "Use the ＋ row at the bottom to add new entries. "
            "Click **Generate Dataloader from Table** to build Excel from this data."
        )
        edited_df = st.data_editor(
            df_edit,
            use_container_width=True,
            num_rows="dynamic",
            key=f"insp_data_editor_{result_hash}",
            column_config={
                "Circuit":      st.column_config.TextColumn("Circuit",           width="medium"),
                "CML":          st.column_config.TextColumn("CML",               width="small"),
                "Min Reading":  st.column_config.NumberColumn(
                                    "Min Reading (in)", format="%.4f", width="small"),
                "Date":         st.column_config.TextColumn("Date (YYYY-MM-DD)", width="medium"),
                "Equipment ID": st.column_config.TextColumn("Equipment ID",      width="large"),
            },
        )

        gen_from_table_btn = st.button(
            "📊 Generate Dataloader from Table",
            type="primary",
            use_container_width=True,
            key="insp_gen_from_table",
            help="Build APM dataloader Excel from the edited table above.",
        )

        if gen_from_table_btn:
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

    st.info("🔒 **Privacy Notice:** Files are processed in memory only and are not stored on the server.")
    st.markdown("### 📋 Process Flow")

    # ── Step 1: Upload ─────────────────────────────────────────────────────────
    # Lock uploaders when reading is active OR about to start (auto_read pending).
    # Peek at the flag here without popping — Step 2 pops it when it fires the read.
    _uploading_locked = (
        st.session_state.get("insp_reading", False)
        or bool(st.session_state.get("insp_auto_read_pending", False))
    )
    st.markdown("**Step 1 — Upload Inspection Report PDFs**")
    pdf_files = st.file_uploader(
        "UT Inspection Report PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        help="One or more UT thickness inspection report PDFs (e.g. Acuren format)",
        key="insp_pdfs",
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
            key="insp_source",
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
    # Compute BEFORE the button so the label/disabled state is right on upload.
    _is_reading  = st.session_state.get("insp_reading", False)
    _auto_read   = bool(pdf_files and st.session_state.pop("insp_auto_read_pending", False))
    _will_read   = _auto_read and not _is_reading   # about to auto-start
    _btn_busy    = _is_reading or _will_read

    col_read, _ = st.columns([2, 5])
    with col_read:
        read_btn = st.button(
            "⏳ Reading…" if _btn_busy else "📖 Read Reports",
            type="primary",
            disabled=not pdf_files or _btn_busy,
            key="insp_read",
            use_container_width=True,
            help="Re-parse PDFs and refresh the table below.",
        )

    if (read_btn or _auto_read) and pdf_files and not _is_reading:
        st.session_state.insp_reading = True
        try:
            _do_read(pdf_files)
        finally:
            st.session_state.insp_reading = False
        if "insp_read_error" in st.session_state:
            err = st.session_state.pop("insp_read_error")
            st.error(f"❌ {err}")

    # ── Step 3: Results (fragment — reruns independently on table edits) ──────
    st.markdown("**Step 3 — Review, Edit & Generate Dataloader**")
    _render_results_section()

    st.divider()
    with st.expander("ℹ️ Help & OCR vs LLM"):
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
