"""Call OpenAI-compatible API (AI Builders) for structured plan JSON."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from backend.llm_config import get_api_key, get_chat_base_url


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{[\s\S]*\}\s*$", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    m2 = re.search(r"\{[\s\S]*\}", text)
    if m2:
        try:
            return json.loads(m2.group(0))
        except json.JSONDecodeError:
            return None
    return None


def call_plan_llm(system_prompt: str, user_prompt: str, model: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    api_key = get_api_key()
    if not api_key:
        return None, "AI_BUILDER_TOKEN not configured"

    from openai import OpenAI

    client = OpenAI(base_url=get_chat_base_url(), api_key=api_key)

    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=4096,
    )

    try:
        resp = client.chat.completions.create(**kwargs, response_format={"type": "json_object"})
    except Exception as e1:
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e2:
            return None, f"{e1!s}; fallback: {e2!s}"

    choice = resp.choices[0] if resp.choices else None
    if not choice:
        return None, "No completion choice"
    msg = choice.message
    content = getattr(msg, "content", None) or ""
    parsed = _extract_json_object(content)
    if parsed is None:
        return None, "Model did not return parseable JSON"
    return parsed, None
