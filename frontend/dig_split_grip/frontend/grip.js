/**
 * Streamlit custom component: draggable vertical splitter (updates Python on mouseup).
 * Uses streamlit-component-lib from esm.sh (bundles deps for iframe).
 */
import { Streamlit } from "https://esm.sh/streamlit-component-lib@2.0.0?bundle";

const el = document.createElement("div");
el.style.cssText = [
  "width:100%",
  "min-height:800px",
  "height:100%",
  "box-sizing:border-box",
  "cursor:col-resize",
  "border-radius:6px",
  "background:linear-gradient(180deg,#7a7a7a 0%,#4d4d4d 45%,#4d4d4d 55%,#7a7a7a 100%)",
  "border:1px solid #2a2a2a",
  "box-shadow:inset 0 0 0 1px rgba(255,255,255,0.12)",
].join(";");
el.title = "Drag horizontally, release to resize map vs workbook";

let ratio = 0.5;
let dragging = false;
let startX = 0;
let startRatio = 0.5;
/** Cached at drag start — avoids reading window.top on every mousemove (reduces jank). */
let dragRefWidth = 1200;

function clamp(x, a, b) {
  return Math.max(a, Math.min(b, x));
}

function measureRefWidth() {
  try {
    return window.top.innerWidth || window.parent.innerWidth || window.innerWidth || 1200;
  } catch (_) {
    return window.innerWidth || 1200;
  }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event) => {
  const detail = event.detail || {};
  const args = detail.args !== undefined ? detail.args : detail;
  const r = args && typeof args.default_ratio === "number" ? args.default_ratio : undefined;
  if (typeof r === "number" && !Number.isNaN(r)) {
    ratio = clamp(r, 0.15, 0.85);
    startRatio = ratio;
  }
});

Streamlit.setComponentReady();
Streamlit.setFrameHeight(820);

function startDrag(clientX) {
  dragging = true;
  startX = clientX;
  startRatio = ratio;
  dragRefWidth = measureRefWidth();
}

el.addEventListener("mousedown", (ev) => {
  startDrag(ev.clientX);
  ev.preventDefault();
});

el.addEventListener(
  "touchstart",
  (ev) => {
    if (ev.touches.length !== 1) return;
    startDrag(ev.touches[0].clientX);
    ev.preventDefault();
  },
  { passive: false },
);

function onMove(ev) {
  if (!dragging) return;
  const w = dragRefWidth || 1200;
  const d = (ev.clientX - startX) / w;
  ratio = clamp(startRatio + d, 0.15, 0.85);
}

function onEnd() {
  if (!dragging) return;
  dragging = false;
  // Skip full Streamlit rerun if the user barely moved (major source of lag).
  if (Math.abs(ratio - startRatio) < 0.004) return;
  Streamlit.setComponentValue(ratio);
}

window.addEventListener("mousemove", onMove);
window.addEventListener("mouseup", onEnd);
window.addEventListener("blur", onEnd);
window.addEventListener("touchmove", (ev) => {
  if (!dragging || ev.touches.length !== 1) return;
  onMove({ clientX: ev.touches[0].clientX });
  ev.preventDefault();
}, { passive: false });
window.addEventListener("touchend", onEnd);
window.addEventListener("touchcancel", onEnd);

document.body.style.margin = "0";
document.body.appendChild(el);
