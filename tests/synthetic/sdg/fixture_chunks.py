"""Build RAG text chunks from existing RDS synthetic fixtures (000–014)."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tests.synthetic.rds_postgres.scenario_loader import ScenarioFixture, load_all_scenarios


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, max_chars: int, overlap: int = 0) -> list[str]:
    text = _norm_ws(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    if overlap >= max_chars:
        raise ValueError("overlap_chars must be less than max_chars_per_chunk")
    step = max_chars - overlap
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + max_chars])
        start += step
    return chunks


def _performance_insights_digest(pi: Mapping[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"window: {pi.get('start_time')} — {pi.get('end_time')}")
    db_load = pi.get("db_load") or {}
    vals = db_load.get("values") or []
    if vals:
        lines.append(f"db_load avg series: min={min(vals):.2f} max={max(vals):.2f} (no per-point dump)")
    for row in (pi.get("top_sql") or [])[:6]:
        stmt = str(row.get("statement", ""))[:400]
        lines.append(f"top_sql ({row.get('db_load_avg')}%): {stmt}")
        for w in (row.get("wait_events") or [])[:5]:
            lines.append(f"  wait {w.get('name')} ({w.get('db_load_avg')}%)")
    for w in (pi.get("top_wait_events") or [])[:8]:
        lines.append(f"top_wait: {w.get('name')} ({w.get('db_load_avg')}%)")
    for u in (pi.get("top_users") or [])[:5]:
        lines.append(f"top_user: {u.get('name')} ({u.get('db_load_avg')}%)")
    return "\n".join(lines)


def scenario_to_document(fx: ScenarioFixture, cfg_fixtures: dict[str, Any]) -> str:
    """Single human-readable scenario card for embedding (metrics names only, no raw CW arrays)."""
    m = fx.metadata
    ak = fx.answer_key
    parts: list[str] = []

    parts.append(f"# Fixture {fx.scenario_id}")
    parts.append(fx.problem_md)

    lines_meta = [
        f"failure_mode: {m.failure_mode}",
        f"instance_class: {m.instance_class}",
        f"region: {m.region}",
        f"engine: {m.engine} {m.engine_version}",
        f"severity: {m.severity}",
        f"scenario_difficulty: {m.scenario_difficulty}",
        f"available_evidence: {', '.join(m.available_evidence)}",
    ]
    if m.adversarial_signals:
        lines_meta.append(f"adversarial_signals: {', '.join(m.adversarial_signals)}")
    if m.depends_on:
        lines_meta.append(f"depends_on: {m.depends_on}")
    parts.append("\n## Metadata\n" + "\n".join(lines_meta))

    parts.append("\n## Answer rubric")
    parts.append(f"root_cause_category: {ak.root_cause_category}")
    parts.append(f"required_keywords: {ak.required_keywords}")
    if ak.forbidden_categories:
        parts.append(f"forbidden_categories: {list(ak.forbidden_categories)}")
    if ak.forbidden_keywords:
        parts.append(f"forbidden_keywords: {list(ak.forbidden_keywords)}")
    if ak.optimal_trajectory:
        parts.append(f"optimal_trajectory: {list(ak.optimal_trajectory)}")
    parts.append(f"max_investigation_loops: {ak.max_investigation_loops}")
    if ak.ruling_out_keywords:
        parts.append(f"ruling_out_keywords: {list(ak.ruling_out_keywords)}")

    if cfg_fixtures.get("include_answer_narrative", True):
        parts.append("\n## Gold narrative (model_response)\n" + ak.model_response)

    ev = fx.evidence
    if cfg_fixtures.get("include_rds_event_messages", True) and ev.rds_events:
        msgs = [str(e.get("message", "")) for e in ev.rds_events if e.get("message")]
        if msgs:
            parts.append("\n## RDS event messages\n" + "\n".join(f"- {x}" for x in msgs))

    if cfg_fixtures.get("include_performance_insights_digest", True) and ev.performance_insights:
        parts.append("\n## Performance insights digest\n" + _performance_insights_digest(ev.performance_insights))

    if cfg_fixtures.get("include_cloudwatch_metric_names", True) and ev.rds_metrics:
        results = ev.rds_metrics.get("metric_data_results") or []
        names = sorted({str(r.get("metric_name")) for r in results if r.get("metric_name")})
        if names:
            parts.append("\n## CloudWatch metrics present\n" + ", ".join(names))

    return "\n".join(parts)


def iter_fixture_chunk_pairs(
    fixtures_root: Path,
    cfg: dict[str, Any],
) -> list[tuple[str, str]]:
    """Return ``(source_id, text)`` for every chunk from all numbered scenario dirs."""
    fx_cfg = cfg.get("chunking", {}).get("fixtures", {})
    max_c = int(fx_cfg.get("max_chars_per_chunk", 2800))
    overlap = int(fx_cfg.get("overlap_chars", 250))

    pairs: list[tuple[str, str]] = []
    for fx in load_all_scenarios(fixtures_root):
        doc = scenario_to_document(fx, fx_cfg)
        for i, ch in enumerate(chunk_text(doc, max_c, overlap)):
            pairs.append((f"fixtures/{fx.scenario_id}#{i}", ch))
    return pairs


def write_chunk_manifest(path: Path, pairs: list[tuple[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for source, text in pairs:
            f.write(json.dumps({"source": source, "text": text}, ensure_ascii=False) + "\n")
