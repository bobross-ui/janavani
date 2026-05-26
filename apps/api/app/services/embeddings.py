"""Embeddings service — lazy-loads sentence-transformers for semantic clustering.

The model is loaded once at first call and cached for the process lifetime.
When the model is unavailable (e.g., not installed, or AI_PROVIDER=local),
a fallback returns None — clustering falls back to Jaccard token overlap.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL = None
_MODEL_NAME = "intfloat/multilingual-e5-small"  # 118 MB, 384-dim


def _get_model():
    """Load the embedding model lazily. Returns None if unavailable."""
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "sentence-transformers not installed; embeddings disabled. "
            "Install with: pip install sentence-transformers"
        )
        return None
    try:
        _MODEL = SentenceTransformer(_MODEL_NAME)
        logger.info("Loaded embedding model: %s", _MODEL_NAME)
    except Exception as exc:
        logger.warning("Failed to load embedding model %s: %s", _MODEL_NAME, exc)
        return None
    return _MODEL


def embed(text: str) -> Optional[list[float]]:
    """Compute an embedding vector for *text*.

    Returns a 384-dim list of floats, or None if the model is unavailable.
    """
    model = _get_model()
    if model is None:
        return None
    # Prepend "query: " for e5 models (improves retrieval quality)
    vec = model.encode(f"query: {text}", normalize_embeddings=True)
    return vec.tolist()


def embed_to_json(text: str) -> Optional[str]:
    """Compute embedding and serialise to JSON. Returns None if unavailable."""
    vec = embed(text)
    if vec is None:
        return None
    return json.dumps(vec)


def parse_embedding_json(json_str: Optional[str]) -> Optional[list[float]]:
    """Parse a JSON-serialised embedding back to a list of floats."""
    if not json_str:
        return None
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return None


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors (any norm).

    Does NOT assume L2-normalised inputs — computes full cosine.
    Returns a value in [-1, 1]; values near 1 indicate high similarity.
    """
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def update_centroid(
    current: Optional[list[float]],
    new: list[float],
    weight: int,
) -> list[float]:
    """Incremental mean of embeddings for cluster centroid update.

    Parameters
    ----------
    current : list[float] or None
        Current centroid embedding (None on first contribution).
    new : list[float]
        New grievance embedding.
    weight : int
        Number of embeddings already in the centroid (before this one).

    Returns
    -------
    list[float]
        Updated centroid (not normalised — caller normalises if needed).
    """
    if current is None:
        return list(new)
    n = weight + 1
    w_old = weight / n
    w_new = 1.0 / n
    return [w_old * c + w_new * nv for c, nv in zip(current, new)]
