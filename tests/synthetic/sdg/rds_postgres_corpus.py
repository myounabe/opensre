"""Chunk the entire ``tests/synthetic/rds_postgres`` tree for RAG (Nomic index).

Text files (.yml, .yaml, .json, .md, .sh) are read relative to the suite root. Python
harness files are skipped. ``cloudwatch_metrics.json`` can be digested (structure + stats
per series) to avoid bloating the index with duplicate time series.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from tests.synthetic.sdg.fixture_chunks import chunk_text

_CORPUS_SUFFIXES = frozenset({".yml", ".yaml", ".json", ".md", ".sh"})

# Suite infrastructure, not fixture evidence for RAG.
def _should_skip_file(suite_root: Path, path: Path) -> bool:
    if not path.is_file():
        return True
    try:
        path.relative_to(suite_root)
    except ValueError:
        return True
    if path.suffix.lower() == ".py":
        return True
    if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
        return True
    return path.suffix.lower() not in _CORPUS_SUFFIXES


def iter_corpus_files(suite_root: Path) -> Iterator[Path]:
    """All indexable non-Python text files under the RDS synthetic suite."""
    suite_root = suite_root.resolve()
    for path in sorted(suite_root.rglob("*")):
        if _should_skip_file(suite_root, path):
            continue
        yield path


def digest_cloudwatch_metrics_json(raw: str) -> str:
    """Compress CW fixture to metric metadata and value summaries (no full arrays)."""
    data = json.loads(raw)
    lines: list[str] = [
        "file: cloudwatch_metrics.json",
        f"namespace: {data.get('namespace')}",
        f"period: {data.get('period')}",
        f"start_time: {data.get('start_time')}",
        f"end_time: {data.get('end_time')}",
    ]
    for r in data.get("metric_data_results") or []:
        vals = [float(x) for x in (r.get("values") or []) if x is not None]
        ts = r.get("timestamps") or []
        lines.append(
            f"metric_name={r.get('metric_name')} id={r.get('id')} stat={r.get('stat')} unit={r.get('unit')}"
        )
        dims = r.get("dimensions") or []
        if dims:
            lines.append(f"  dimensions={dims}")
        lines.append(f"  n_points={len(vals)}")
        if ts:
            lines.append(f"  first_ts={ts[0]} last_ts={ts[-1]}")
        if vals:
            lines.append(
                f"  values min={min(vals):.6g} max={max(vals):.6g} last={vals[-1]:.6g}"
            )
    return "\n".join(lines)


def file_as_corpus_text(path: Path, *, digest_cloudwatch: bool) -> str:
    raw = path.read_text(encoding="utf-8")
    if digest_cloudwatch and path.name == "cloudwatch_metrics.json":
        try:
            return digest_cloudwatch_metrics_json(raw)
        except (json.JSONDecodeError, TypeError, ValueError):
            return raw
    return raw


def iter_rds_suite_chunk_pairs(
    suite_root: Path,
    cfg: dict[str, Any],
) -> list[tuple[str, str]]:
    """``(source_id, text)`` for every chunk, with sources like ``rds_postgres/shared/asset.yml#0``."""
    corpus_cfg = cfg.get("corpus", {})
    digest_cw = bool(corpus_cfg.get("digest_cloudwatch_metrics", True))
    chunking = cfg.get("chunking", {})
    max_c_raw = corpus_cfg.get("file_chunk_max_chars")
    if max_c_raw is None:
        max_c_raw = chunking.get("knowledge_base_max_chars", 1200)
    overlap_raw = corpus_cfg.get("file_chunk_overlap_chars")
    if overlap_raw is None:
        overlap_raw = chunking.get("knowledge_base_overlap_chars", 0)
    max_c = int(max_c_raw)
    overlap = int(overlap_raw)

    suite_root = suite_root.resolve()
    prefix = "rds_postgres"

    pairs: list[tuple[str, str]] = []
    for path in iter_corpus_files(suite_root):
        rel = path.relative_to(suite_root).as_posix()
        try:
            body = file_as_corpus_text(path, digest_cloudwatch=digest_cw)
        except OSError:
            continue
        header = f"[{prefix}/{rel}]\n\n"
        for i, ch in enumerate(chunk_text(header + body, max_c, overlap)):
            if ch.strip():
                pairs.append((f"{prefix}/{rel}#{i}", ch))
    return pairs


def supplement_sdg_knowledge_base_chunks(
    kb_dir: Path,
    cfg: dict[str, Any],
) -> list[tuple[str, str]]:
    """Optional chunks from ``sdg/knowledge_base`` (metric_behavior, templates)."""
    chunk_cfg = cfg.get("chunking", {})
    max_c = int(chunk_cfg.get("knowledge_base_max_chars", 1200))
    overlap = int(chunk_cfg.get("knowledge_base_overlap_chars", 0))

    rows: list[tuple[str, str]] = []
    if not kb_dir.is_dir():
        return rows

    for path in sorted(kb_dir.glob("metric_behavior/**/*.md")):
        rel = f"sdg_kb/{path.relative_to(kb_dir).as_posix()}"
        raw = path.read_text(encoding="utf-8")
        for i, ch in enumerate(chunk_text(raw, max_c, overlap)):
            if ch:
                rows.append((f"{rel}#{i}", ch))

    for name in ("instance_profiles.yml", "postgres_log_templates.yml"):
        p = kb_dir / name
        if p.is_file():
            raw = p.read_text(encoding="utf-8")
            for i, ch in enumerate(chunk_text(raw, max_c, overlap)):
                if ch:
                    rows.append((f"sdg_kb/{name}#{i}", ch))
    return rows
