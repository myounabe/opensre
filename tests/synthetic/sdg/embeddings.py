"""Nomic embedding helpers for RAG index build and diversity checks.

Uses task prefixes recommended for ``nomic-ai/nomic-embed-text-v1``:
  - documents: ``search_document: {text}``
  - queries: ``search_query: {text}``

Requires optional dependency: ``pip install 'opensre[sdg]'`` (sentence-transformers + torch).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

NOMIC_MODEL_ID = "nomic-ai/nomic-embed-text-v1"


def _require_sentence_transformers() -> Any:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        msg = (
            "SDG embeddings require sentence-transformers. Install with: "
            "pip install 'opensre[sdg]'"
        )
        raise ImportError(msg) from e
    return SentenceTransformer


@lru_cache(maxsize=1)
def load_embedder(model_id: str = NOMIC_MODEL_ID) -> Any:
    """Load and cache the sentence-transformers model (downloads on first use)."""
    SentenceTransformer = _require_sentence_transformers()
    return SentenceTransformer(model_id, trust_remote_code=True)


def embed_documents(texts: list[str], model_id: str = NOMIC_MODEL_ID) -> Any:
    """Embed corpus chunks with the Nomic document prefix."""
    import numpy as np

    model = load_embedder(model_id)
    prefixed = [f"search_document: {t}" for t in texts]
    vectors = model.encode(
        prefixed,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def embed_query(text: str, model_id: str = NOMIC_MODEL_ID) -> Any:
    """Embed a single query with the Nomic query prefix."""
    import numpy as np

    model = load_embedder(model_id)
    v = model.encode(
        [f"search_query: {text}"],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(v[0], dtype=np.float32)


def cosine_similarity(a: Any, b: Any) -> float:
    """Cosine similarity for L2-normalized vectors (dot product)."""
    import numpy as np

    return float(np.dot(a, b))
