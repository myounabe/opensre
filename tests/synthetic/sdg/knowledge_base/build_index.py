#!/usr/bin/env python3
"""Chunk the RDS synthetic suite + optional SDG KB supplement; build ``vector_index.npz``.

The **primary corpus** is the full ``tests/synthetic/rds_postgres`` tree (see
``rds_postgres_corpus.py``). Optional chunks from ``sdg/knowledge_base/`` (metric behavior,
templates) are controlled by ``corpus.include_sdg_knowledge_base_supplement``.

Usage (from repo root):
  pip install 'opensre[sdg]'
  python tests/synthetic/sdg/knowledge_base/build_index.py
  python tests/synthetic/sdg/knowledge_base/build_index.py --config path/to/sdg_config.yml

Writes ``vector_index.npz`` (path from config ``paths.vector_index_file``).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from tests.synthetic.sdg import embeddings as emb  # noqa: E402
from tests.synthetic.sdg.config import load_sdg_config, resolve_paths  # noqa: E402
from tests.synthetic.sdg.fixture_chunks import write_chunk_manifest  # noqa: E402
from tests.synthetic.sdg.rds_postgres_corpus import (  # noqa: E402
    iter_rds_suite_chunk_pairs,
    supplement_sdg_knowledge_base_chunks,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SDG vector index (Nomic).")
    parser.add_argument("--config", type=Path, default=None, help="sdg_config.yml path")
    args = parser.parse_args()

    cfg = load_sdg_config(args.config)
    paths = resolve_paths(cfg)
    suite_dir = paths["rds_fixtures_dir"]
    kb_dir = paths["sdg_knowledge_base_dir"]
    out = paths["vector_index_file"]

    all_chunks: list[str] = []
    sources: list[str] = []

    for src, text in iter_rds_suite_chunk_pairs(suite_dir, cfg):
        all_chunks.append(text)
        sources.append(src)

    if cfg.get("corpus", {}).get("include_sdg_knowledge_base_supplement", True):
        for src, text in supplement_sdg_knowledge_base_chunks(kb_dir, cfg):
            all_chunks.append(text)
            sources.append(src)

    if not all_chunks:
        print("No chunks; check rds_fixtures_dir and corpus settings.")
        raise SystemExit(1)

    export = cfg.get("paths", {}).get("chunk_manifest_export")
    if export:
        exp_path = Path(export)
        if not exp_path.is_absolute():
            exp_path = paths["repo_root"] / exp_path
        write_chunk_manifest(exp_path, list(zip(sources, all_chunks, strict=True)))

    model_id = cfg.get("embedding", {}).get("model_id", emb.NOMIC_MODEL_ID)
    if cfg.get("logging", {}).get("verbose"):
        print(f"Embedding {len(all_chunks)} chunks with {model_id} ...")
    vectors = emb.embed_documents(all_chunks, model_id=model_id)

    import numpy as np

    out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        out,
        embeddings=vectors,
        texts=np.array(all_chunks, dtype=object),
        sources=np.array(sources, dtype=object),
    )
    print(f"Wrote {len(all_chunks)} chunks -> {out}")


if __name__ == "__main__":
    main()
