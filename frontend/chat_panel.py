"""Chat with Chen — floating FAB + modal dialog (full-width main layout)."""

import os
import textwrap
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


def render_chat_panel(*, in_modal: bool = False):
    """
    Chat UI (model, messages, input). When ``in_modal=True``, outer title is omitted
    (dialog already shows "Chat with Chen").
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

    if not in_modal:
        st.markdown("#### 💬 Chat with Chen")
        st.markdown("---")

    selected_idx = st.selectbox(
        "⚙️ LLM Model",
        range(len(model_ids)),
        format_func=lambda i: model_names[i],
        key="chat_model_select",
    )
    st.session_state.chat_model = model_ids[selected_idx]

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


@st.dialog("💬 Chat with Chen", width="large")
def _chat_dialog():
    render_chat_panel(in_modal=True)
    if st.button("Close", key="chat_modal_close", type="secondary"):
        st.rerun()


def _render_chat_fab_link():
    """Fixed bottom-right FAB using HTML so it sits on the viewport (not trapped in a narrow block)."""
    st.markdown(
        textwrap.dedent("""
        <style>
          a#chen-chat-fab {
            position: fixed !important;
            bottom: 22px !important;
            right: 22px !important;
            z-index: 2147483000 !important;
            width: 58px !important;
            height: 58px !important;
            border-radius: 50% !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            text-decoration: none !important;
            font-size: 26px !important;
            line-height: 1 !important;
            cursor: pointer !important;
            background: linear-gradient(145deg, #5b6ee8, #7c3fb8) !important;
            color: #fff !important;
            box-shadow: 0 4px 18px rgba(0,0,0,0.28) !important;
            border: 2px solid rgba(255,255,255,0.35) !important;
            transition: transform 0.15s ease, box-shadow 0.15s ease !important;
          }
          a#chen-chat-fab:hover {
            transform: scale(1.07) !important;
            box-shadow: 0 6px 22px rgba(0,0,0,0.32) !important;
          }
        </style>
        <a href="?open_chat=1" id="chen-chat-fab" target="_self" title="Chat with Chen">💬</a>
        """).strip(),
        unsafe_allow_html=True,
    )


def render_floating_chat_shell():
    """
    Call once at the bottom of each page (after main content).
    Opens chat in a modal when the user clicks the FAB or visits with ``?open_chat=1``.
    """
    _ensure_chat_state()
    if st.query_params.get("open_chat") == "1":
        try:
            st.query_params.pop("open_chat")
        except Exception:
            pass
        _chat_dialog()
    _render_chat_fab_link()


def render_chat_expander(right_col, visible: bool):
    """Deprecated no-op — use ``render_floating_chat_shell()`` once at the bottom of the page."""
    _ = (right_col, visible)
