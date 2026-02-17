"""JSON schemas for LLM tool calls (OpenAI-compatible format)."""

# OpenAI-compatible function schema for web_search
WEB_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": "Search the web for current information, news, facts, or real-time data. Use when the user asks about recent events, sports, weather, or anything that requires up-to-date information.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up on the web",
                }
            },
            "required": ["query"],
        },
    },
}
