"""Tests for fixture chunking (no sentence-transformers)."""

from __future__ import annotations

from tests.synthetic.rds_postgres.scenario_loader import load_all_scenarios
from tests.synthetic.sdg.config import load_sdg_config, resolve_paths
from tests.synthetic.sdg.fixture_chunks import chunk_text, scenario_to_document
from tests.synthetic.sdg.rds_postgres_corpus import iter_rds_suite_chunk_pairs


def test_chunk_text_overlap_produces_multiple() -> None:
    text = "abcdefgh" * 100
    parts = chunk_text(text, max_chars=50, overlap=10)
    assert len(parts) > 1
    assert all(len(p) <= 50 for p in parts)


def test_all_numbered_fixtures_are_chunked() -> None:
    cfg = load_sdg_config()
    paths = resolve_paths(cfg)
    pairs = iter_rds_suite_chunk_pairs(paths["rds_fixtures_dir"], cfg)
    fixture_ids = {
        p[0].split("/")[1]
        for p in pairs
        if p[0].startswith("rds_postgres/") and p[0].split("/")[1][:3].isdigit()
    }
    scenarios = load_all_scenarios(paths["rds_fixtures_dir"])
    assert len(scenarios) == 15
    assert len(fixture_ids) == 15
    for fx in scenarios:
        assert fx.scenario_id in fixture_ids


def test_scenario_document_contains_failure_mode() -> None:
    cfg = load_sdg_config()
    paths = resolve_paths(cfg)
    fx = load_all_scenarios(paths["rds_fixtures_dir"])[0]
    doc = scenario_to_document(fx, cfg["chunking"]["fixtures"])
    assert fx.metadata.failure_mode in doc
    assert "Gold narrative" in doc or "model_response" in doc
