"""Web search tool using AI Builders Space MCP search API (Tavily)."""

import os
from typing import Any

import httpx

# AI Builders Space base URL and auth
SEARCH_BASE_URL = os.getenv(
    "AI_BUILDERS_BASE_URL", "https://space.ai-builders.com/backend"
)
AI_BUILDER_TOKEN = os.getenv("AI_BUILDER_TOKEN", "")


def web_search(query: str, max_results: int = 6) -> str:
    """
    Search the web for information using the AI Builders Space search API (Tavily).

    Args:
        query: Search query string.
        max_results: Maximum number of results per query (1-20, default 6).

    Returns:
        Search results as formatted text. Includes combined_answer if available,
        otherwise formatted results from each query.
    """
    if not AI_BUILDER_TOKEN:
        return "Error: AI_BUILDER_TOKEN is not configured. Set it in your environment."

    url = f"{SEARCH_BASE_URL.rstrip('/')}/v1/search/"
    headers = {
        "Authorization": f"Bearer {AI_BUILDER_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"keywords": [query], "max_results": min(max(1, max_results), 20)}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPError as e:
        return f"Search failed: {str(e)}"
    except Exception as e:
        return f"Search error: {str(e)}"

    return _format_search_response(data)


def _format_search_response(data: dict[str, Any]) -> str:
    """Format SearchResponse into readable text."""
    if data.get("combined_answer"):
        return data["combined_answer"]

    parts = []
    for qr in data.get("queries", []):
        keyword = qr.get("keyword", "")
        resp = qr.get("response", {})
        if isinstance(resp, dict):
            results = resp.get("results", [])
            answer = resp.get("answer")
            if answer:
                parts.append(f"Answer for '{keyword}': {answer}")
            for r in results[:6]:
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")[:300]
                parts.append(f"- {title}\n  {url}\n  {content}...")
        else:
            parts.append(str(resp))

    if data.get("errors"):
        for err in data["errors"]:
            parts.append(f"Error for '{err.get('keyword', '')}': {err.get('error', '')}")

    return "\n\n".join(parts) if parts else "No results found."
