"""Synthetic data generation (SDG) pipeline: RAG-grounded scenario specs → fixture files.

RAG indexes the full ``tests/synthetic/rds_postgres`` tree; generated outputs go under ``sdg/generated/``
in the same on-disk layout as hand-authored scenarios.
Embeddings use ``nomic-ai/nomic-embed-text-v1`` when the ``opensre[sdg]`` extra is installed.
"""

from __future__ import annotations
