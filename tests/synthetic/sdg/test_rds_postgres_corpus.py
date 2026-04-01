"""Tests for full-suite RAG corpus walking (no sentence-transformers)."""

from __future__ import annotations

from tests.synthetic.rds_postgres.scenario_loader import load_all_scenarios
from tests.synthetic.sdg.config import load_sdg_config, resolve_paths
from tests.synthetic.sdg.rds_postgres_corpus import iter_corpus_files, iter_rds_suite_chunk_pairs


def test_corpus_includes_every_numbered_scenario_file() -> None:
    cfg = load_sdg_config()
    paths = resolve_paths(cfg)
    suite = paths["rds_fixtures_dir"]
    scenarios = load_all_scenarios(suite)
    assert len(scenarios) == 15
    all_sources = {s for s, _ in iter_rds_suite_chunk_pairs(suite, cfg)}
    for fx in scenarios:
        assert any(
            s.startswith(f"rds_postgres/{fx.scenario_id}/scenario.yml#") for s in all_sources
        ), f"missing scenario.yml chunk for {fx.scenario_id}"


def test_corpus_skips_python_harness() -> None:
    paths = resolve_paths(load_sdg_config())
    suite = paths["rds_fixtures_dir"]
    rels = {p.relative_to(suite).as_posix() for p in iter_corpus_files(suite)}
    assert "scenario_loader.py" not in rels
    assert "run_suite.py" not in rels
    assert "test_suite.py" not in rels
