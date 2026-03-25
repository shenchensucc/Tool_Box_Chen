"""Streamlit custom component: vertical drag grip to set map/workbook column split (ratio on mouseup)."""

from __future__ import annotations

import os

import streamlit.components.v1 as components

_frontend = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend")
_dig_split_grip = components.declare_component("dig_split_grip", path=_frontend)


def dig_split_grip(*, default_ratio: float = 0.5, key: str | None = None) -> float | None:
    """
    Render a narrow vertical drag strip. While dragging, the grip tracks horizontally;
    on mouseup the new left-column fraction (0.15–0.85) is sent to Streamlit.

    Returns ``None`` until the user has completed a drag; keep the desired ratio in
    ``st.session_state`` and pass it as ``default_ratio`` each run.
    """
    return _dig_split_grip(
        default_ratio=float(default_ratio),
        key=key,
        default=None,
        tab_index=-1,
    )
