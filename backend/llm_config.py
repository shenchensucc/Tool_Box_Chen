"""LLM provider configuration for Chat with Chen."""

import os

# AI Builders Space API (MCP)
AI_BUILDERS_BASE_URL = os.getenv("AI_BUILDERS_BASE_URL", "https://space.ai-builders.com/backend")
AI_BUILDER_TOKEN = os.getenv("AI_BUILDER_TOKEN", "")

# Model id -> display name. Add more as needed.
LLM_OPTIONS = [
    {"id": "grok-4-fast", "name": "Grok-4-Fast (default)"},
    {"id": "supermind-agent-v1", "name": "Supermind Agent (web search + Gemini)"},
    {"id": "deepseek", "name": "DeepSeek"},
    {"id": "gpt-5", "name": "GPT-5"},
    {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
    {"id": "gemini-3-flash-preview", "name": "Gemini 3 Flash"},
    {"id": "kimi-k2.5", "name": "Kimi K2.5"},
]

DEFAULT_MODEL = "grok-4-fast"


def get_chat_base_url() -> str:
    """Base URL for chat completions (OpenAI-compatible)."""
    return f"{AI_BUILDERS_BASE_URL.rstrip('/')}/v1"


def get_api_key() -> str:
    """API key for LLM requests. Reads fresh from env each call."""
    return os.getenv("AI_BUILDER_TOKEN", "")
