"""Retrieve chunks from a Nomic-built ``vector_index.npz`` (cosine similarity).

Reranker: when ``rag.reranker.enabled`` is true in config, reranking is not implemented yet;
callers get a clear error. For this corpus size, bi-encoder top-k is usually sufficient — see
``sdg_config.yml`` comments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from tests.synthetic.sdg import embeddings as emb
from tests.synthetic.sdg.config import load_sdg_config, resolve_paths


class RetrievalResult:
    __slots__ = ("texts", "sources", "scores")

    def __init__(self, texts: list[str], sources: list[str], scores: list[float]) -> None:
        self.texts = texts
        self.sources = sources
        self.scores = scores


def _apply_reranker_placeholder(cfg: dict[str, Any]) -> None:
    r_cfg = cfg.get("rag", {}).get("reranker", {})
    if r_cfg.get("enabled"):
        raise NotImplementedError(
            "rag.reranker.enabled is true but no cross-encoder is wired. "
            "Set reranker.enabled: false in sdg_config.yml, or implement reranking."
        )


def retrieve(
    query: str,
    index_path: Path | None = None,
    config_path: Path | None = None,
    *,
    override_top_k: int | None = None,
) -> RetrievalResult:
    """Embed ``query`` with Nomic (query prefix) and return top chunks by cosine similarity."""
    cfg = load_sdg_config(config_path)
    _apply_reranker_placeholder(cfg)

    paths = resolve_paths(cfg)
    idx_file = index_path or paths["vector_index_file"]
    if not idx_file.is_file():
        raise FileNotFoundError(
            f"Vector index missing: {idx_file}. Build with: python .../knowledge_base/build_index.py"
        )

    data = np.load(idx_file, allow_pickle=True)
    mat = np.asarray(data["embeddings"], dtype=np.float32)
    texts = [str(x) for x in data["texts"]]
    sources = [str(x) for x in data["sources"]]

    model_id = cfg.get("embedding", {}).get("model_id", emb.NOMIC_MODEL_ID)
    q = np.asarray(emb.embed_query(query, model_id=model_id), dtype=np.float32)
    sims = mat @ q

    min_sim = float(cfg.get("rag", {}).get("min_similarity", 0.0))
    top_k = int(override_top_k or cfg.get("rag", {}).get("retrieval_top_k", 8))

    order = np.argsort(-sims)
    picked_texts: list[str] = []
    picked_sources: list[str] = []
    picked_scores: list[float] = []
    for idx in order:
        i = int(idx)
        s = float(sims[i])
        if s < min_sim:
            continue
        picked_texts.append(texts[i])
        picked_sources.append(sources[i])
        picked_scores.append(s)
        if len(picked_texts) >= top_k:
            break

    return RetrievalResult(picked_texts, picked_sources, picked_scores)


def format_context_block(result: RetrievalResult) -> str:
    """Join retrieved chunks into one markdown block for LLM system context."""
    blocks: list[str] = []
    for t, s, score in zip(result.texts, result.sources, result.scores, strict=True):
        blocks.append(f"### {s} (similarity={score:.3f})\n\n{t}")
    return "\n\n---\n\n".join(blocks)
