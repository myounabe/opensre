"""Unit tests for SDG validator (no embedding dependencies)."""

from __future__ import annotations

from pathlib import Path

from tests.synthetic.sdg.validator import SpecValidator


def _spec(**kwargs: object) -> dict:
    base = {
        "scenario_id": "test",
        "instance_class": "db.r6g.2xlarge",
        "time_window_minutes": 20,
        "metric_signals": [
            {
                "metric": "CPUUtilization",
                "role": "primary_signal",
                "pattern": "ramp_then_flat",
                "ramp_start_min": 0,
                "ramp_end_min": 5,
                "base_value": 22.0,
                "peak_value": 91.0,
                "noise_frac": 0.05,
            },
        ],
        "log_lines": [
            {"at_min": 1, "severity": "ERROR", "message": "deadlock detected", "detail": ""},
        ],
        "rds_events": [],
        "answer": {"required_keywords": ["deadlock"]},
    }
    base.update(kwargs)
    return base  # type: ignore[return-value]


def test_validator_passes_minimal_spec() -> None:
    v = SpecValidator(instance_profiles_path=Path(__file__).parent / "knowledge_base" / "instance_profiles.yml")
    errs = v.validate(_spec())
    assert errs == []


def test_validator_connection_peak_over_max() -> None:
    v = SpecValidator(instance_profiles_path=Path(__file__).parent / "knowledge_base" / "instance_profiles.yml")
    spec = _spec(
        metric_signals=[
            {
                "metric": "CPUUtilization",
                "role": "primary_signal",
                "pattern": "jittered",
                "mean": 20.0,
                "noise_frac": 0.05,
            },
            {
                "metric": "DatabaseConnections",
                "role": "confounder",
                "pattern": "blip",
                "blip_start_min": 0,
                "blip_end_min": 5,
                "baseline": 10.0,
                "peak": 99999.0,
                "noise_frac": 0.05,
            },
        ],
    )
    errs = v.validate(spec)
    assert any("exceeds max_connections" in e for e in errs)


def test_validator_missing_keyword() -> None:
    v = SpecValidator(instance_profiles_path=Path(__file__).parent / "knowledge_base" / "instance_profiles.yml")
    spec = _spec(answer={"required_keywords": ["not-in-logs"]})
    errs = v.validate(spec)
    assert any("not-in-logs" in e for e in errs)


def test_validator_log_outside_window() -> None:
    v = SpecValidator(instance_profiles_path=Path(__file__).parent / "knowledge_base" / "instance_profiles.yml")
    spec = _spec(log_lines=[{"at_min": 25, "severity": "LOG", "message": "x", "detail": ""}])
    errs = v.validate(spec)
    assert any("outside time window" in e for e in errs)
