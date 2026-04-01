"""Orchestrate SDG stages (stub): wire Claude + RAG + renderer + validator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from tests.synthetic.sdg.config import load_sdg_config, resolve_paths
from tests.synthetic.sdg.renderer import (
    render_cloudwatch_skeleton,
    render_metric_signal,
    spec_series_count,
)
from tests.synthetic.sdg.validator import SpecValidator


def generated_scenario_dir(
    scenario_id: str,
    *,
    config_path: Path | None = None,
) -> Path:
    """Output directory for one generated scenario (mirrors ``rds_postgres/NNN-slug/`` layout)."""
    paths = resolve_paths(load_sdg_config(config_path))
    sid = "".join(c if c.isalnum() or c in "-_" else "-" for c in scenario_id.strip())
    return paths["generated_scenarios_dir"] / sid


def render_spec_metrics(spec: dict[str, Any]) -> dict[str, Any]:
    """Stage 4: build cloudwatch_metrics.json content from metric_signals only."""
    scenario_id = spec.get("scenario_id", "sdg-draft")
    start = spec.get("start_time", "2026-04-01T14:00:00Z")
    n = spec_series_count(spec)
    period = int(spec.get("metric_period_sec", 60))
    # end time: n minutes from start (approximate, matches timestamps() in generator)
    from datetime import datetime, timedelta

    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
    end = (dt + timedelta(seconds=(n - 1) * period)).strftime("%Y-%m-%dT%H:%M:%SZ")

    results: list[dict[str, Any]] = []
    for sig in spec.get("metric_signals", []):
        results.append(render_metric_signal(sig, n, start, scenario_id))
    return render_cloudwatch_skeleton(start, end, period, results)


def validate_spec(spec: dict[str, Any]) -> list[str]:
    return SpecValidator().validate(spec)


def write_fixture_preview(
    spec: dict[str, Any],
    out_dir: Path | None = None,
    *,
    config_path: Path | None = None,
) -> Path:
    """Write partial fixture files under ``sdg/generated/<scenario_id>/`` (or ``out_dir``).

    Full generation should eventually emit the same filenames as hand-authored scenarios:
    ``scenario.yml``, ``answer.yml``, ``alert.json``, ``cloudwatch_metrics.json``,
    ``rds_events.json``, ``performance_insights.json``. This stub writes metrics plus the
    raw SDG spec for inspection.
    """
    if out_dir is None:
        out_dir = generated_scenario_dir(str(spec.get("scenario_id", "sdg-draft")), config_path=config_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    cw = render_spec_metrics(spec)
    (out_dir / "cloudwatch_metrics.json").write_text(json.dumps(cw, indent=2))
    (out_dir / "scenario_spec.yml").write_text(yaml.safe_dump(spec, sort_keys=False))
    return out_dir
