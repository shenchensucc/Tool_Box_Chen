"""
Skills Overview — Documents Cursor IDE skills and app capabilities for developers.
Skills live in .cursor/skills/ and are shared via git for consistent development across machines.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend_utils import (
    apply_custom_styling,
    display_header,
    display_sidebar_navigation,
    get_layout_main,
    set_page_config,
)
from chat_panel import render_floating_chat_shell

# Page configuration
set_page_config("Skills Overview - Chen's Toolbox", "🧠")
apply_custom_styling()

# Custom Sidebar Navigation
display_sidebar_navigation()

main = get_layout_main()

with main:
    display_header(
        "🧠 Skills Overview",
        "Cursor IDE skills and app capabilities — for developers and further development",
    )

    st.markdown(
        """
        This page documents the **Cursor IDE skills** embedded in this project and the **app tools** they support.
        Skills are stored in `.cursor/skills/` and committed to git so they are available on any machine.
        """
    )

    st.markdown("---")

    # ─── Section 1: Cursor IDE Skills ─────────────────────────────────────────
    st.markdown("## 📌 Cursor IDE Skills")

    st.markdown(
        """
        **Skills** are AI guidance files that help Cursor (and other AI assistants) work effectively on specific features.
        When you ask for help improving the inspection parser, fixing extraction bugs, or adding new report formats,
        the AI can load the relevant skill and follow the documented workflow.
        """
    )

    with st.expander("🔧 Inspection Report Parser Iteration", expanded=True):
        st.markdown(
            """
            **When to use:** Improving parser accuracy, fixing extraction bugs, or adding support for new report formats.

            **Key files:**
            - `backend/tml/inspection_report_parser.py` — Parser logic (pdfplumber, OCR fallback)
            - `dev_tools/inspection_report_ground_truth.py` — Streamlit UI to create ground truth
            - `dev_tools/validate_ground_truth.py` — Validate parser vs ground truth
            - `dev_tools/ground_truth_data/*.json` — Expected readings per PDF
            """
        )

        st.markdown("**Workflow:**")
        st.markdown(
            """
            ```
            Load PDF → Dev Tool (mark wrong/add missing) → Save ground truth
                                ↓
            Validate → Parser changes → Validate (repeat)
            ```
            """
        )

        st.markdown("**Validation commands:**")
        st.code(
            """
python dev_tools/validate_ground_truth.py
python dev_tools/validate_ground_truth.py --fixtures-only
            """,
            language="bash",
        )

    st.markdown("---")

    # ─── Section 2: App Tools Overview ─────────────────────────────────────────
    st.markdown("## 🛠️ App Tools Overview")

    st.markdown(
        """
        High-level flow of the main tools and how they connect. Use this to understand the toolbox structure.
        """
    )

    st.markdown("### Tool Categories & Flow")

    # Flowchart using HTML/CSS for a clean visual
    st.markdown(
        """
        <div style="font-family: monospace; font-size: 0.9rem; line-height: 1.8; padding: 1rem; background: #f8f9fa; border-radius: 8px; border: 1px solid #e9ecef;">
        <strong>🏭 Facility</strong><br>
        &nbsp;&nbsp;├─ TML Data Loader &nbsp;&nbsp;&nbsp;→ Batch process thickness monitoring data<br>
        &nbsp;&nbsp;├─ De-active CML &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ Mark CMLs as inactive<br>
        &nbsp;&nbsp;└─ Inspection Report Loader → Parse PDFs → Read summaries / Generate dataloader<br>
        <br>
        <strong>🛢️ Pipeline</strong><br>
        &nbsp;&nbsp;├─ Dig Package Visual Tool → Visualize dig package Excel data<br>
        &nbsp;&nbsp;├─ ILI Visual Tool &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;→ Upload Excel or paste ILI data<br>
        &nbsp;&nbsp;├─ Metal Loss Assessment &nbsp;→ Assess metal loss from ILI data<br>
        &nbsp;&nbsp;├─ Metal Loss Mass Assessment → Mass assessment workflows<br>
        &nbsp;&nbsp;└─ Dig Package Generator &nbsp;&nbsp;→ Generate dig packages for excavations<br>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Inspection Report Loader — Detailed Flow")

    st.markdown(
        """
        <div style="font-family: monospace; font-size: 0.85rem; line-height: 1.9; padding: 1rem; background: #f0f7ff; border-radius: 8px; border: 1px solid #cce5ff;">
        <strong>User uploads PDFs</strong><br>
        &nbsp;&nbsp;&nbsp;&nbsp;│<br>
        &nbsp;&nbsp;&nbsp;&nbsp;├─► <strong>Read Reports</strong> &nbsp;&nbsp;→ Parse → Show summary (Circuit, CML, Min Reading, Date)<br>
        &nbsp;&nbsp;&nbsp;&nbsp;│<br>
        &nbsp;&nbsp;&nbsp;&nbsp;└─► <strong>Generate Dataloader</strong> → Parse → Optional Source Excel → APM Measurements Excel<br>
        <br>
        <strong>Parser pipeline:</strong> pdfplumber (tables/text) → OCR fallback if needed → Dedupe & output
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # ─── Section 3: Adding New Skills ─────────────────────────────────────────
    st.markdown("## ➕ Adding New Skills")

    st.markdown(
        """
        To add a skill for a new feature or workflow:

        1. Create `.cursor/skills/<skill-name>/SKILL.md`
        2. Use the YAML frontmatter: `name`, `description`
        3. Document workflow, key files, and common fixes
        4. Commit and push so the skill is available on all machines

        See the [create-skill](https://cursor.com/docs/context/skills) guide for structure and best practices.
        """
    )

    st.markdown("---")

    # Footer
    st.markdown(
        """
        <div style="text-align: center; color: #95a5a6; padding: 1rem 0;">
            <p>Skills help AI assistants work consistently across your team and machines.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

render_floating_chat_shell()
