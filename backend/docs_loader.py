"""Load and search tool documentation for RAG context."""

from pathlib import Path

from backend.docs_registry import DOC_REGISTRY, get_doc_path


def load_all_docs() -> dict[str, str]:
    """
    Load all docs from the registry. Returns {id: content}.
    """
    result = {}
    for entry in DOC_REGISTRY:
        path = get_doc_path(entry)
        if path.exists():
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                doc_id = entry["id"]
                title = entry.get("title", doc_id)
                # Prepend title for context
                result[doc_id] = f"# {title}\n\n{content}"
            except Exception:
                pass
    return result


def search_docs(query: str, docs: dict[str, str] | None = None, top_k: int = 3) -> list[tuple[str, str, float]]:
    """
    Simple keyword-based search over docs. Returns list of (doc_id, content, score).
    Score is count of query terms found (case-insensitive).
    """
    if docs is None:
        docs = load_all_docs()

    query_terms = [t.lower().strip() for t in query.split() if t.strip()]
    if not query_terms:
        return []

    scored: list[tuple[str, str, float]] = []
    for doc_id, content in docs.items():
        content_lower = content.lower()
        score = sum(1 for t in query_terms if t in content_lower)
        if score > 0:
            scored.append((doc_id, content, float(score)))

    scored.sort(key=lambda x: (-x[2], len(x[1])))
    return scored[:top_k]


def get_relevant_context(query: str, max_chars: int = 8000) -> str:
    """
    Get relevant doc chunks for a user query, formatted for LLM context.
    """
    docs = load_all_docs()
    hits = search_docs(query, docs=docs, top_k=5)

    parts = []
    total = 0
    for doc_id, content, _ in hits:
        # Truncate long docs to fit context
        chunk = content[:max_chars // len(hits)] if len(hits) > 1 else content[:max_chars]
        if total + len(chunk) > max_chars:
            chunk = chunk[: max_chars - total]
        parts.append(chunk)
        total += len(chunk)
        if total >= max_chars:
            break

    if not parts:
        return ""

    return "\n\n---\n\n".join(parts)
