"""Stage 5 validation: instance profile bounds, causal hints, log window, keyword grounding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SpecValidator:
    def __init__(self, instance_profiles_path: Path | None = None) -> None:
        kb = Path(__file__).parent / "knowledge_base"
        path = instance_profiles_path or (kb / "instance_profiles.yml")
        self._profiles: dict[str, Any] = {}
        if path.is_file():
            self._profiles = yaml.safe_load(path.read_text()) or {}

    def validate(self, spec: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        ic = spec.get("instance_class", "")
        profile = self._profiles.get(ic, {})

        for signal in spec.get("metric_signals", []):
            mname = signal.get("metric", "")
            if mname == "DatabaseConnections":
                peak = float(signal.get("peak", signal.get("peak_value", 0)))
                max_c = profile.get("max_connections")
                if max_c is not None and peak > max_c:
                    errors.append(
                        f"DatabaseConnections peak {peak} exceeds max_connections {max_c} for {ic}"
                    )
            if mname == "CPUUtilization":
                peak = float(signal.get("peak_value", signal.get("peak", 0)))
                if peak > 100:
                    errors.append("CPUUtilization cannot exceed 100%")

        primary = [s for s in spec.get("metric_signals", []) if s.get("role") == "primary_signal"]
        if not primary:
            errors.append("No primary_signal declared in metric_signals")

        tw = int(spec.get("time_window_minutes", 0))
        for log in spec.get("log_lines", []):
            at_m = int(log.get("at_min", -1))
            if tw and at_m >= tw:
                errors.append(f"log_line at_min={at_m} outside time window ({tw} min)")

        for ev in spec.get("rds_events", []):
            at_m = int(ev.get("at_min", -1))
            if tw and at_m >= tw:
                errors.append(f"rds_event at_min={at_m} outside time window ({tw} min)")

        answer = spec.get("answer") or {}
        keywords = answer.get("required_keywords", [])
        parts: list[str] = []
        for item in spec.get("log_lines", []) + spec.get("rds_events", []):
            parts.append(str(item.get("message", "")))
            parts.append(str(item.get("detail", "")))
        all_text = " ".join(parts).lower()
        for kw in keywords:
            if str(kw).lower() not in all_text:
                errors.append(
                    f"required_keyword {kw!r} not found in log_lines or rds_events text"
                )

        return errors
