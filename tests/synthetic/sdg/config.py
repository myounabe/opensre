"""Load ``sdg_config.yml`` with defaults for paths and RAG parameters."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_SDG_DIR = Path(__file__).resolve().parent
_DEFAULT_CONFIG_PATH = _SDG_DIR / "sdg_config.yml"

# Defaults merged on top of user YAML so partial configs work.
_DEFAULTS: dict[str, Any] = {
    "paths": {
        "repo_root": None,
        "rds_fixtures_dir": None,
        "sdg_knowledge_base_dir": None,
        "vector_index_file": None,
        "chunk_manifest_export": None,
        "generated_scenarios_dir": None,
    },
    "corpus": {
        "include_sdg_knowledge_base_supplement": True,
        "digest_cloudwatch_metrics": True,
        "file_chunk_max_chars": None,
        "file_chunk_overlap_chars": None,
    },
    "embedding": {"model_id": "nomic-ai/nomic-embed-text-v1"},
    "chunking": {
        "knowledge_base_max_chars": 1200,
        "knowledge_base_overlap_chars": 0,
        "fixtures": {
            "max_chars_per_chunk": 2800,
            "overlap_chars": 250,
            "include_answer_narrative": True,
            "include_performance_insights_digest": True,
            "include_cloudwatch_metric_names": True,
            "include_rds_event_messages": True,
        },
    },
    "rag": {
        "retrieval_top_k": 8,
        "min_similarity": 0.0,
        "reranker": {"enabled": False, "model_id": None, "pool_size": 32},
    },
    "generation": {
        "scenarios_to_generate": 15,
        "default_failure_mode": None,
        "default_instance_class": "db.r6g.2xlarge",
        "default_difficulty": 2,
        "default_time_window_minutes": 20,
        "max_validation_retries": 3,
        "max_diversity_retries": 5,
        "parallel_workers": 1,
    },
    "diversity": {
        "embedding_reject_threshold": 0.85,
        "track_in_matrix": {
            "failure_mode": True,
            "instance_class": True,
            "difficulty": True,
            "confounder_type": True,
        },
    },
    "logging": {"verbose": False},
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = deepcopy(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)  # type: ignore[assignment]
        else:
            out[k] = v
    return out


def load_sdg_config(path: Path | None = None) -> dict[str, Any]:
    """Return merged config dict. Path defaults to ``tests/synthetic/sdg/sdg_config.yml``."""
    p = path or _DEFAULT_CONFIG_PATH
    merged = deepcopy(_DEFAULTS)
    if p.is_file():
        user = yaml.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(user, dict):
            merged = _deep_merge(merged, user)
    return merged


def resolve_paths(cfg: dict[str, Any]) -> dict[str, Path]:
    """Fill null path entries relative to repo root (tests/synthetic/sdg/../../..)."""
    repo_root = cfg["paths"].get("repo_root")
    root = Path(repo_root).resolve() if repo_root else _SDG_DIR.parent.parent.parent

    paths = cfg["paths"]
    fixtures = paths.get("rds_fixtures_dir")
    kb = paths.get("sdg_knowledge_base_dir")
    v_index = paths.get("vector_index_file")
    gen = paths.get("generated_scenarios_dir")

    return {
        "repo_root": root,
        "rds_fixtures_dir": Path(fixtures).resolve() if fixtures else root / "tests" / "synthetic" / "rds_postgres",
        "sdg_knowledge_base_dir": Path(kb).resolve() if kb else root / "tests" / "synthetic" / "sdg" / "knowledge_base",
        "vector_index_file": Path(v_index).resolve()
        if v_index
        else root / "tests" / "synthetic" / "sdg" / "knowledge_base" / "vector_index.npz",
        "generated_scenarios_dir": Path(gen).resolve()
        if gen
        else root / "tests" / "synthetic" / "sdg" / "generated",
    }
