"""Render structured scenario specs into CloudWatch-style metric series using existing primitives."""

from __future__ import annotations

from typing import Any

from tests.synthetic.rds_postgres.shared.generate_fixtures import (
    BASELINE_DEFS,
    blip_series,
    flat_then_collapse,
    jittered_series,
    ramp_then_flat,
    timestamps,
)


def _make_seed(label: str, start_iso: str) -> int:
    h = 0
    for c in label + ":" + start_iso:
        h = (h * 31 + ord(c)) & 0xFFFFFFFF
    return h or 1


def build_metric_data_result(
    metric_name: str,
    series_id: str,
    instance_dim: str,
    stat: str,
    unit: str,
    ts: list[str],
    values: list[float],
) -> dict[str, Any]:
    return {
        "id": series_id,
        "label": metric_name,
        "metric_name": metric_name,
        "dimensions": [{"Name": "DBInstanceIdentifier", "Value": instance_dim}],
        "stat": stat,
        "unit": unit,
        "status_code": "Complete",
        "timestamps": ts,
        "values": values,
    }


def _baseline_def_for_metric(metric_name: str) -> dict[str, Any] | None:
    for d in BASELINE_DEFS:
        if d["metric_name"] == metric_name:
            return d
    return None


def render_metric_signal(
    signal: dict[str, Any],
    n: int,
    start_iso: str,
    scenario_id: str,
) -> dict[str, Any]:
    """Generate one ``MetricDataResult``-shaped dict from a spec signal block."""
    pattern = signal["pattern"]
    metric = signal["metric"]
    seed = _make_seed(scenario_id + ":" + metric, start_iso)
    ts = timestamps(start_iso, n)

    defn = _baseline_def_for_metric(metric)
    dim = defn["dim"] if defn else signal.get("dimension_instance", "payments-prod")
    series_id = signal.get("id") or (defn["id"] if defn else f"m_{metric.lower()}")
    stat = signal.get("stat") or (defn["stat"] if defn else "Average")
    unit = signal.get("unit") or (defn["unit"] if defn else "None")

    if pattern == "ramp_then_flat":
        values = ramp_then_flat(
            seed,
            float(signal["base_value"]),
            float(signal["peak_value"]),
            int(signal["ramp_start_min"]),
            int(signal["ramp_end_min"]),
            n,
            noise_frac=float(signal.get("noise_frac", 0.05)),
        )
    elif pattern == "blip":
        values = blip_series(
            seed,
            float(signal["baseline"]),
            float(signal["peak"]),
            int(signal["blip_start_min"]),
            int(signal["blip_end_min"]),
            n,
            noise_frac=float(signal.get("noise_frac", 0.08)),
        )
    elif pattern == "jittered":
        values = jittered_series(
            seed,
            float(signal["mean"]),
            n,
            noise_frac=float(signal.get("noise_frac", 0.10)),
            floor=signal.get("floor"),
            ceil=signal.get("ceil"),
        )
    elif pattern == "flat_then_collapse":
        values = flat_then_collapse(
            seed,
            float(signal["start_value"]),
            float(signal["end_value"]),
            int(signal["collapse_start_min"]),
            n,
            noise_frac=float(signal.get("noise_frac", 0.02)),
            round_to=int(signal.get("round_to", 0)),
        )
    else:
        raise ValueError(f"Unknown metric pattern: {pattern}")

    return build_metric_data_result(metric, series_id, dim, stat, unit, ts, values)


def render_cloudwatch_skeleton(
    start_iso: str,
    end_iso: str,
    period_sec: int,
    metric_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble top-level ``cloudwatch_metrics.json`` structure."""
    return {
        "namespace": "AWS/RDS",
        "period": period_sec,
        "start_time": start_iso,
        "end_time": end_iso,
        "metric_data_results": metric_results,
    }


def spec_window_minutes(spec: dict[str, Any]) -> int:
    return int(spec.get("time_window_minutes", 15))


def spec_series_count(spec: dict[str, Any]) -> int:
    """One sample per minute at 60s period, matching existing fixtures."""
    n = spec_window_minutes(spec)
    if n <= 0:
        raise ValueError("time_window_minutes must be positive")
    return n
