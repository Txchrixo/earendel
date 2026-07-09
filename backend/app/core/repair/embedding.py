"""Phase 2 — Embedding-based semantic retrieval for the Repair Flywheel.

This module provides TF-IDF-based semantic similarity for repair knowledge
base queries. It replaces the previous exact-match SQL lookup with real
retrieval-augmented repair: failures are embedded as text, and the KB is
searched by cosine similarity rather than categorical equality.

**Honesty note:** This is TF-IDF + cosine similarity (via scikit-learn, which
is already installed), NOT transformer-based embeddings (sentence-transformers
would require a ~2GB torch install). TF-IDF is real semantic retrieval — it
catches "download invoice" ↔ "get invoice PDF" similarity that exact SQL
matching misses — but it's weaker than transformer embeddings on paraphrase
and synonym detection. Upgrading to `sentence-transformers` with a model like
`all-MiniLM-L6-v2` or `bge-small-en-v1.5` is a documented future improvement.

Academic grounding:
- RAP-Gen (retrieval-augmented patch generation) — the canonical RAG-for-repair pattern
- ReAPR (retrieval-augmented program repair) — RAG for APR
- Semter (FSE 2023) — intent abstraction for cross-client transfer
- Similo (TOSEM 2023) — element-matching features for locator repair
- WAREX (arXiv:2510.03285, 2025) — LLM self-healing doesn't hold under real instability
"""
from __future__ import annotations

import logging
import threading
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Lazy-loaded globals — only import sklearn when first needed.
_tfidf_vectorizer = None
_tfidf_matrix = None  # type: ignore[var-annotated]
_kb_texts: list[str] = []
_kb_entries: list[dict] = []
_cache_lock = threading.Lock()
_cache_version: int = -1

# Minimum cosine similarity to consider a match (0.0–1.0).
MIN_SIMILARITY: float = 0.15


def build_embedding_text(
    target_domain: str,
    widget_type: str,
    intention: str,
    failed_selector: str,
    error_message: str = "",
    page_text: str = "",
) -> str:
    """Build the canonical text used for semantic embedding.

    The text combines all available signals about a failure:
    - target_domain (e.g. "acme.com")
    - widget_type (e.g. "button")
    - intention (e.g. "download")
    - failed_selector (e.g. "button[data-invoice-download]")
    - error_message (e.g. "selector not found: button[data-invoice-download]")
    - page_text (optional, from the browser adapter — visible text near the failure)

    The page_text is truncated to 500 chars to keep the embedding focused.
    """
    parts = [
        f"domain: {target_domain}",
        f"widget: {widget_type}",
        f"intention: {intention}",
        f"selector: {failed_selector}",
    ]
    if error_message:
        parts.append(f"error: {error_message[:200]}")
    if page_text:
        parts.append(f"page: {page_text[:500]}")
    return " | ".join(parts)


async def rebuild_index(all_entries: list[dict]) -> int:
    """Rebuild the TF-IDF index from all active KB entries.

    Called when the KB changes (insert, update, deprecate). Thread-safe.
    Returns the number of entries indexed.
    """
    global _tfidf_vectorizer, _tfidf_matrix, _kb_texts, _kb_entries, _cache_version

    active = [e for e in all_entries if e.get("status") == "active"]
    texts = [e.get("embeddingText", "") or _fallback_text(e) for e in active]

    with _cache_lock:
        _kb_entries = active
        _kb_texts = texts
        _cache_version += 1

        if not texts:
            _tfidf_vectorizer = None
            _tfidf_matrix = None
            return 0

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity

            _tfidf_vectorizer = TfidfVectorizer(
                lowercase=True,
                ngram_range=(1, 2),
                stop_words="english",
                sublinear_tf=True,
                min_df=1,
            )
            _tfidf_matrix = _tfidf_vectorizer.fit_transform(texts)
            logger.info("repair KB TF-IDF index rebuilt: %d entries", len(texts))
            return len(texts)
        except Exception as exc:
            logger.warning("TF-IDF index rebuild failed: %s", exc)
            _tfidf_vectorizer = None
            _tfidf_matrix = None
            return 0


def _fallback_text(entry: dict) -> str:
    """Build embedding text from entry fields when embeddingText is empty."""
    return build_embedding_text(
        target_domain=entry.get("targetDomain", ""),
        widget_type=entry.get("widgetType", ""),
        intention=entry.get("intention", ""),
        failed_selector=entry.get("failedSelector", ""),
    )


async def search_semantic(
    query_text: str,
    top_k: int = 5,
    min_similarity: float = MIN_SIMILARITY,
) -> list[tuple[dict, float]]:
    """Search the KB by semantic similarity to `query_text`.

    Returns a list of `(entry, similarity_score)` tuples, sorted by
    similarity descending. Only entries with similarity >= min_similarity
    are returned. If the index is empty or unavailable, returns [].
    """
    if _tfidf_vectorizer is None or _tfidf_matrix is None:
        return []

    try:
        from sklearn.metrics.pairwise import cosine_similarity

        query_vec = _tfidf_vectorizer.transform([query_text])
        sims = cosine_similarity(query_vec, _tfidf_matrix).flatten()

        results: list[tuple[dict, float]] = []
        for i, sim in enumerate(sims):
            if sim >= min_similarity and i < len(_kb_entries):
                results.append((_kb_entries[i], float(sim)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    except Exception as exc:
        logger.warning("semantic search failed: %s", exc)
        return []


def get_index_version() -> int:
    """Return the current index version (for cache invalidation checks)."""
    return _cache_version


def get_index_size() -> int:
    """Return the number of entries in the current index."""
    return len(_kb_texts)
