#!/usr/bin/env python3
"""
Verify that the LLM outputs a valid tool call when asked "Who won the Super Bowl?".

Uses the web_search tool schema and AI Builders Space API.
Does NOT execute the tool or implement the full agent loop - only verifies the response format.

Usage:
    Set AI_BUILDER_TOKEN in environment, then:
    python scripts/verify_tool_call.py
"""

import json
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI

from backend.llm_config import get_chat_base_url, get_api_key
from backend.tools.schemas import WEB_SEARCH_SCHEMA


def verify_tool_call() -> bool:
    """Send 'Who won the Super Bowl?' and verify LLM returns valid tool_calls."""
    api_key = get_api_key()
    if not api_key:
        print("ERROR: AI_BUILDER_TOKEN not set in environment")
        return False

    client = OpenAI(base_url=get_chat_base_url(), api_key=api_key)

    messages = [
        {
            "role": "system",
            "content": "You have access to the web_search tool. Use it when the user asks about current events or facts.",
        },
        {"role": "user", "content": "Who won the Super Bowl?"},
    ]

    response = client.chat.completions.create(
        model="grok-4-fast",
        messages=messages,
        tools=[WEB_SEARCH_SCHEMA],
        tool_choice="auto",
        max_tokens=1024,
    )

    choice = response.choices[0] if response.choices else None
    if not choice:
        print("ERROR: No completion returned")
        return False

    msg = choice.message
    tool_calls = getattr(msg, "tool_calls", None) or []

    if not tool_calls:
        print("FAIL: LLM did not return any tool_calls")
        print(f"Response content: {getattr(msg, 'content', '')}")
        return False

    tc = tool_calls[0]
    fn = getattr(tc, "function", None)
    if not fn:
        print("FAIL: First tool call has no 'function'")
        return False

    name = fn.name if hasattr(fn, "name") else fn.get("name")
    if name != "web_search":
        print(f"FAIL: Expected tool name 'web_search', got '{name}'")
        return False

    args_str = fn.arguments if hasattr(fn, "arguments") else fn.get("arguments", "{}")
    try:
        args = json.loads(args_str) if isinstance(args_str, str) else args_str
    except json.JSONDecodeError:
        print(f"FAIL: Invalid JSON in arguments: {args_str}")
        return False

    if "query" not in args:
        print(f"FAIL: 'query' not in arguments: {args}")
        return False

    print("PASS: LLM returned valid tool call")
    print(f"  Tool: {name}")
    print(f"  Query: {args.get('query', '')}")
    return True


if __name__ == "__main__":
    ok = verify_tool_call()
    sys.exit(0 if ok else 1)
