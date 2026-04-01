"""Diversity controls: coverage matrix tracking and embedding deduplication (Nomic)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.synthetic.sdg import embeddings as emb


@dataclass
class CoverageMatrix:
    """Tracks how many scenarios were generated per stratified cell."""

    counts: dict[str, int] = field(default_factory=dict)

    def key(
        self,
        failure_mode: str,
        instance_class: str,
        difficulty: int,
        confounder_type: str,
    ) -> str:
        return f"{failure_mode}|{instance_class}|d{difficulty}|{confounder_type}"

    def record(
        self,
        failure_mode: str,
        instance_class: str,
        difficulty: int,
        confounder_type: str,
    ) -> None:
        k = self.key(failure_mode, instance_class, difficulty, confounder_type)
        self.counts[k] = self.counts.get(k, 0) + 1

    def least_covered_key(self, candidates: list[str]) -> str:
        if not candidates:
            raise ValueError("candidates empty")
        return min(candidates, key=lambda c: self.counts.get(c, 0))


def max_cosine_vs_bank(narrative: str, bank_vectors: list[Any], model_id: str = emb.NOMIC_MODEL_ID) -> float:
    """Return max cosine similarity against existing scenario embeddings (normalized dot)."""
    import numpy as np

    q = emb.embed_query(narrative, model_id=model_id)
    if not bank_vectors:
        return 0.0
    mat = np.stack(bank_vectors, axis=0)
    sims = mat @ q
    return float(np.max(sims))


def is_too_similar(narrative: str, bank_vectors: list[Any], threshold: float = 0.85) -> bool:
    return max_cosine_vs_bank(narrative, bank_vectors) > threshold
