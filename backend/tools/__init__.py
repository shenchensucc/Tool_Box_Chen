"""Backend tools for chat bot (web search, etc.)."""

from backend.tools.web_search import web_search
from backend.tools.schemas import WEB_SEARCH_SCHEMA

__all__ = ["web_search", "WEB_SEARCH_SCHEMA"]
