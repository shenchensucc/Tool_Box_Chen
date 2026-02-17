"""Chat with Chen - collapsible right-side chat panel."""

import os
from typing import Any

import httpx
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

# Chen's greeting when chat is empty
CHEN_GREETING = "This is Chen, how can I help with engineering tools?"


def _ensure_chat_state():
    """Initialize chat session state."""
    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []
    if "chat_model" not in st.session_state:
        st.session_state.chat_model = "grok-4-fast"
    if "chat_models_list" not in st.session_state:
        st.session_state.chat_models_list = []


def _fetch_models() -> list[dict]:
    """Fetch available LLM models from backend."""
    try:
        r = httpx.get(f"{BACKEND_URL}/api/chat/models", timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            return data.get("models", [])
    except Exception:
        pass
    return [
        {"id": "grok-4-fast", "name": "Grok-4-Fast (default)"},
        {"id": "supermind-agent-v1", "name": "Supermind Agent"},
        {"id": "deepseek", "name": "DeepSeek"},
        {"id": "gpt-5", "name": "GPT-5"},
    ]


def _call_chat_api(messages: list[dict], model: str) -> str | None:
    """Call backend /api/chat and return assistant content."""
    try:
        with httpx.Client(timeout=60.0) as client:
            r = client.post(
                f"{BACKEND_URL}/api/chat",
                json={"messages": messages, "model": model},
            )
            r.raise_for_status()
            data = r.json()
            return data.get("content")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            return f"**Chat not configured:** {detail}\n\nSet `AI_BUILDER_TOKEN` in your `.env` file (copy from `.env.example`)."
        return f"Error {e.response.status_code}: {str(e)}"
    except httpx.HTTPError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error: {str(e)}"


def render_chat_panel():
    """
    Render the collapsible Chat with Chen panel.
    Use inside an expander or a right column.
    """
    _ensure_chat_state()

    models = _fetch_models()
    if models and not st.session_state.chat_models_list:
        st.session_state.chat_models_list = models

    model_options = st.session_state.chat_models_list or [
        {"id": "grok-4-fast", "name": "Grok-4-Fast (default)"},
    ]
    model_ids = [m["id"] for m in model_options]
    model_names = [m["name"] for m in model_options]

    st.markdown("#### 💬 Chat with Chen")
    selected_idx = st.selectbox(
        "LLM Model",
        range(len(model_ids)),
        format_func=lambda i: model_names[i],
        key="chat_model_select",
    )
    st.session_state.chat_model = model_ids[selected_idx]

    st.markdown("---")

    # Scrollable message area (fixed height, ChatGPT-like)
    with st.container(height=360):
        if not st.session_state.chat_messages:
            with st.chat_message("assistant"):
                st.markdown(f"*{CHEN_GREETING}*")
        for msg in st.session_state.chat_messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                with st.chat_message("user"):
                    st.markdown(content)
            else:
                with st.chat_message("assistant"):
                    st.markdown(content)

    # Input at bottom (ChatGPT-style)
    prompt = st.chat_input("Ask about tools or anything...")
    if prompt:
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.spinner("Thinking..."):
            api_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state.chat_messages
            ]
            response = _call_chat_api(api_messages, st.session_state.chat_model)
            if response:
                st.session_state.chat_messages.append(
                    {"role": "assistant", "content": response}
                )
        st.rerun()

    if st.session_state.chat_messages and st.button("Clear chat", key="chat_clear"):
        st.session_state.chat_messages = []
        st.rerun()


def render_chat_panel_with_controls():
    """
    Render Chat with Chen panel with hide button and width slider.
    Call this inside the right column when chat is visible.
    """
    render_chat_panel()

    st.markdown("---")
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("◀ Hide", key="chat_hide", help="Collapse chat to right edge"):
            st.session_state.chat_panel_visible = False
            st.rerun()
    with col_b:
        w = st.slider("Width", 1, 4, st.session_state.chat_panel_width, key="chat_width_slider", help="Adjust panel width (1=narrow, 4=wide)")
        if w != st.session_state.chat_panel_width:
            st.session_state.chat_panel_width = w
            st.rerun()


def render_chat_expander(right_col, visible: bool):
    """
    Render Chat with Chen in right column, or collapsed tab when hidden.
    visible: from get_layout_with_chat() return.
    """
    if visible:
        with right_col:
            render_chat_panel_with_controls()
    else:
        with right_col:
            # Collapsed: narrow tab on right edge to expand
            if st.button("💬 Chat", key="chat_show_tab", help="Show Chat with Chen"):
                st.session_state.chat_panel_visible = True
                st.rerun()
