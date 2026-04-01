#!/usr/bin/env python3
"""Run SDG pipeline end-to-end: orchestrate all stages and write 6 fixture files.

Usage:
    python tests/synthetic/sdg/run_sdg.py \
      --failure_mode cpu_saturation \
      --instance_class db.r6g.2xlarge \
      --difficulty 2

Output: tests/synthetic/sdg/generated/<scenario_id>/
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import anthropic
import yaml
from dotenv import load_dotenv

from tests.synthetic.rds_postgres.shared.generate_fixtures import (
    jittered_series,
    ramp_then_flat,
    timestamps,
)
from tests.synthetic.sdg.config import load_sdg_config, resolve_paths
from tests.synthetic.sdg.pipeline import render_spec_metrics
from tests.synthetic.sdg.validator import SpecValidator

# Load .env
_REPO_ROOT = Path(__file__).resolve().parents[3]
_ENV_FILE = _REPO_ROOT / ".env"
if _ENV_FILE.exists():
    load_dotenv(_ENV_FILE)


# ─── Constants ────────────────────────────────────────────────────────────────

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

FAILURE_MODE_TEMPLATES = {
    "cpu_saturation": {
        "severity": "critical",
        "alert_name": "CPUSaturation",
        "summary_template": "CPU utilization exceeded threshold and sustained high load on {instance}.",
        "top_sql": [
            {"stmt": "UPDATE orders SET status = $1 WHERE id = $2", "wait": ["CPU", "Lock:relation"]},
            {"stmt": "DELETE FROM audit_log WHERE created_at < $1", "wait": ["CPU", "IO:WALWrite"]},
            {"stmt": "SELECT COUNT(*) FROM transactions WHERE status = $1", "wait": ["CPU", "IO:DataFileRead"]},
        ],
        "wait_events": ["CPU", "Lock:relation", "IO:WALWrite"],
    },
    "replication_lag": {
        "severity": "critical",
        "alert_name": "RDSReplicationLagHigh",
        "summary_template": "Read replica lag exceeded threshold on {instance}.",
        "top_sql": [
            {"stmt": "INSERT INTO events (type, data) VALUES ($1, $2)", "wait": ["IO:WALWrite"]},
            {"stmt": "UPDATE settlements SET processed = true WHERE batch_id = $1", "wait": ["IO:WALWrite", "CPU"]},
        ],
        "wait_events": ["IO:WALWrite", "CPU"],
    },
    "connection_exhaustion": {
        "severity": "critical",
        "alert_name": "DatabaseConnectionHigh",
        "summary_template": "Database connections exceeded safe limits on {instance}.",
        "top_sql": [
            {"stmt": "SELECT * FROM users WHERE id = $1", "wait": ["IPC:MessageQueueReceive"]},
        ],
        "wait_events": ["IPC:MessageQueueReceive", "Client:ClientRead"],
    },
    "storage_full": {
        "severity": "critical",
        "alert_name": "StorageFull",
        "summary_template": "Free storage space critically low on {instance}.",
        "top_sql": [
            {"stmt": "DELETE FROM log_entries WHERE created_at < $1", "wait": ["IO:DataFileWrite"]},
        ],
        "wait_events": ["IO:DataFileWrite", "IO:WALWrite"],
    },
    "failover": {
        "severity": "critical",
        "alert_name": "FailoverDetected",
        "summary_template": "Database failover occurred on {instance}.",
        "top_sql": [],
        "wait_events": ["IO:WALWrite"],
    },
    "healthy": {
        "severity": "ok",
        "alert_name": "HealthCheck",
        "summary_template": "Database is healthy on {instance}.",
        "top_sql": [],
        "wait_events": [],
    },
}


# ─── Context Loading ──────────────────────────────────────────────────────────


def load_prompt(name: str) -> str:
    """Load prompt file."""
    p = Path(__file__).parent / "prompts" / f"{name}.md"
    return p.read_text()


def build_kb_context(failure_mode: str, instance_class: str) -> str:
    """Load all KB files and format as context block."""
    kb = Path(__file__).parent / "knowledge_base"

    blocks = []

    # Instance profiles
    if (kb / "instance_profiles.yml").exists():
        profiles = (kb / "instance_profiles.yml").read_text()
        blocks.append(f"## Instance Profiles\n\n```yaml\n{profiles}\n```")

    # Postgres log templates
    if (kb / "postgres_log_templates.yml").exists():
        templates = (kb / "postgres_log_templates.yml").read_text()
        blocks.append(f"## Postgres Log Templates\n\n```yaml\n{templates}\n```")

    # Metric behavior docs
    metric_dir = kb / "metric_behavior"
    if metric_dir.exists():
        for doc in sorted(metric_dir.glob("*.md")):
            blocks.append(f"## {doc.stem}\n\n{doc.read_text()}")

    context = "\n\n---\n\n".join(blocks)
    return f"# RETRIEVED_CONTEXT\n\n{context}"


# ─── LLM Calls ────────────────────────────────────────────────────────────────


def call_llm(system: str, user_msg: str, model: str) -> str:
    """Call Claude API."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    msg = client.messages.create(
        model=model,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return msg.content[0].text


def stage1_planning(
    failure_mode: str,
    instance_class: str,
    difficulty: int,
    context: str,
) -> str:
    """Stage 1: Generate causal narrative."""
    print(f"  Stage 1: Planning narrative ({failure_mode}, {instance_class}, difficulty {difficulty})...")
    prompt_text = load_prompt("planning")
    system = f"{prompt_text}\n\n{context}"
    user_msg = f"failure_mode: {failure_mode}\ninstance_class: {instance_class}\ndifficulty: {difficulty}"
    return call_llm(system, user_msg, HAIKU_MODEL)


def stage2_spec_generation(
    failure_mode: str,
    instance_class: str,
    difficulty: int,
    narrative: str,
    context: str,
) -> dict[str, Any]:
    """Stage 2: Generate YAML spec (with retry on validation failure)."""
    print("  Stage 2: Generating spec...")
    prompt_text = load_prompt("spec_generation")
    system = f"{prompt_text}\n\n{context}"
    validator = SpecValidator()
    error_feedback = ""

    for attempt in range(1, 4):
        user_msg = f"## Narrative\n\n{narrative}\n\n## Failure Mode\n\n{failure_mode}\n\ninstance_class: {instance_class}\ndifficulty: {difficulty}"
        if attempt > 1:
            user_msg += f"\n\nFix the following validation errors:\n{error_feedback}"

        spec_yaml = call_llm(system, user_msg, HAIKU_MODEL)

        # Strip markdown code fences if present
        if spec_yaml.startswith("```"):
            lines = spec_yaml.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]  # Remove opening fence
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]  # Remove closing fence
            spec_yaml = "\n".join(lines).strip()

        # Parse & validate
        try:
            spec = yaml.safe_load(spec_yaml)
            if not isinstance(spec, dict):
                raise ValueError("YAML did not parse as dict")

            errors = validator.validate(spec)
            if not errors:
                print(f"    ✓ Spec valid on attempt {attempt}")
                return spec
            else:
                error_feedback = "\n".join(errors)
                print(f"    ✗ Attempt {attempt}: {len(errors)} validation errors, retrying...")
        except Exception as e:
            error_feedback = f"Parse error: {str(e)}"
            print(f"    ✗ Attempt {attempt}: {error_feedback}, retrying...")

    raise ValueError(f"Failed to generate valid spec after 3 retries. Last error: {error_feedback}")


def stage6_answer_key(spec: dict[str, Any]) -> dict[str, Any]:
    """Stage 6: Generate answer key (grader rubric)."""
    print("  Stage 6: Generating answer key...")
    prompt_text = load_prompt("answer_key")
    system = prompt_text
    user_msg = f"# Scenario Spec\n\n```yaml\n{yaml.dump(spec, sort_keys=False)}\n```"
    answer_yaml = call_llm(system, user_msg, SONNET_MODEL)

    # Strip markdown code fences if present
    if answer_yaml.startswith("```"):
        lines = answer_yaml.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]  # Remove opening fence
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]  # Remove closing fence
        answer_yaml = "\n".join(lines).strip()

    try:
        answer = yaml.safe_load(answer_yaml)
        return answer if isinstance(answer, dict) else {}
    except Exception as e:
        print(f"    Warning: failed to parse answer key: {e}")
        return {}


# ─── Fixture Building ──────────────────────────────────────────────────────────


def build_scenario_yml(spec: dict[str, Any]) -> dict[str, Any]:
    """Build scenario.yml from spec."""
    return {
        "schema_version": "1.0",
        "scenario_id": spec.get("scenario_id", "sdg-draft"),
        "engine": "postgres",
        "engine_version": "15",
        "instance_class": spec.get("instance_class", "db.r6g.2xlarge"),
        "region": spec.get("region", "us-east-1"),
        "db_instance_identifier": "payments-prod",
        "db_cluster": spec.get("db_cluster", "payments-cluster"),
        "failure_mode": spec.get("failure_mode", "healthy"),
        "severity": spec.get("severity", "critical"),
        "scenario_difficulty": spec.get("difficulty", 1),
        "adversarial_signals": spec.get("adversarial_signals", []),
        "available_evidence": ["rds_metrics", "rds_events", "performance_insights"],
    }


def build_alert_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Build alert.json from spec."""
    failure_mode = spec.get("failure_mode", "healthy")
    instance = "payments-prod"
    template = FAILURE_MODE_TEMPLATES.get(failure_mode, FAILURE_MODE_TEMPLATES["healthy"])

    summary = template["summary_template"].format(instance=instance)

    return {
        "title": f"[synthetic-rds] {template['alert_name']} On {instance}",
        "state": "alerting" if template["severity"] != "ok" else "resolved",
        "alert_source": "cloudwatch",
        "commonLabels": {
            "alertname": template["alert_name"],
            "severity": template["severity"],
            "pipeline_name": "rds-postgres-synthetic",
            "service": "rds",
            "engine": "postgres",
        },
        "commonAnnotations": {
            "summary": summary,
            "error": spec.get("cause", "Incident detected"),
            "suspected_symptom": spec.get("adversarial_signals", ["fault symptom"])[0] if spec.get("adversarial_signals") else "fault symptom",
            "db_instance_identifier": instance,
            "db_instance": instance,
            "db_cluster": spec.get("db_cluster", "payments-cluster"),
            "read_replica": f"{instance}-replica-1",
            "cloudwatch_region": spec.get("region", "us-east-1"),
            "rds_failure_mode": failure_mode,
            "context_sources": "cloudwatch",
        },
    }


def build_rds_events_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert spec rds_events (at_min) to ISO timestamps."""
    start_iso = spec.get("start_time", "2026-04-01T14:00:00Z")
    time_window = int(spec.get("time_window_minutes", 15))

    # Generate all timestamps
    ts_list = timestamps(start_iso, time_window)

    events = []
    for ev in spec.get("rds_events", []):
        at_min = int(ev.get("at_min", 0))
        if 0 <= at_min < len(ts_list):
            events.append({
                "date": ts_list[at_min],
                "message": ev.get("message", "Database event"),
                "source_identifier": ev.get("source_identifier", "payments-prod"),
                "source_type": ev.get("source_type", "db-instance"),
                "event_categories": ev.get("event_categories", ["notification"]),
            })

    return {"events": events}


def build_performance_insights_json(spec: dict[str, Any]) -> dict[str, Any]:
    """Generate performance_insights.json mimicking the fault pattern."""
    start_iso = spec.get("start_time", "2026-04-01T14:00:00Z")
    time_window = int(spec.get("time_window_minutes", 15))
    failure_mode = spec.get("failure_mode", "healthy")

    ts_list = timestamps(start_iso, time_window)

    # Generate db_load that mirrors the primary signal
    primary_signal = next((s for s in spec.get("metric_signals", []) if s.get("role") == "primary_signal"), None)
    if primary_signal and primary_signal.get("pattern") == "ramp_then_flat":
        db_load = ramp_then_flat(
            hash(spec.get("scenario_id", "")) & 0xFFFFFFFF,
            float(primary_signal.get("base_value", 1.0)),
            float(primary_signal.get("peak_value", 8.0)),
            int(primary_signal.get("ramp_start_min", 2)),
            int(primary_signal.get("ramp_end_min", 5)),
            len(ts_list),
            noise_frac=0.05,
        )
    else:
        db_load = jittered_series(
            hash(spec.get("scenario_id", "")) & 0xFFFFFFFF,
            mean=2.0,
            n=len(ts_list),
            noise_frac=0.1,
            floor=0.5,
            ceil=15.0,
        )

    db_load_avg = float(sum(db_load) / len(db_load))
    template = FAILURE_MODE_TEMPLATES.get(failure_mode, {})

    # Build top SQL
    top_sql = []
    for i, sql_template in enumerate(template.get("top_sql", [])[:3]):
        top_sql.append({
            "statement": sql_template.get("stmt", "SELECT 1"),
            "db_load_avg": max(1.0, db_load_avg * (3 - i) / 3),
            "wait_events": [{"name": w, "type": w.split(":")[0], "db_load_avg": max(0.5, db_load_avg * 0.4 / len(sql_template.get("wait", [])))} for w in sql_template.get("wait", [])],
            "calls_per_sec": 10.0 + i * 5,
        })

    # Top wait events
    top_wait_events = []
    for we in template.get("wait_events", [])[:6]:
        top_wait_events.append({
            "name": we,
            "type": we.split(":")[0],
            "db_load_avg": db_load_avg * 0.3,
        })

    return {
        "db_instance_identifier": "payments-prod",
        "start_time": start_iso,
        "end_time": ts_list[-1],
        "db_load": {
            "timestamps": ts_list,
            "values": [round(float(v), 2) for v in db_load],
            "unit": "db_load|avg",
        },
        "top_sql": top_sql,
        "top_wait_events": top_wait_events,
        "top_users": [
            {"name": "payments_service", "db_load_avg": db_load_avg * 0.7},
            {"name": "settlement_worker", "db_load_avg": db_load_avg * 0.2},
        ],
        "top_hosts": [
            {"id": "10.0.1.15", "db_load_avg": db_load_avg * 0.5},
            {"id": "10.0.1.22", "db_load_avg": db_load_avg * 0.35},
        ],
    }


# ─── Main Pipeline ────────────────────────────────────────────────────────────


def run_pipeline(
    failure_mode: str,
    instance_class: str,
    difficulty: int,
) -> Path:
    """Run full SDG pipeline end-to-end."""
    print("\n🚀 SDG Pipeline")
    print(f"  failure_mode: {failure_mode}")
    print(f"  instance_class: {instance_class}")
    print(f"  difficulty: {difficulty}\n")

    # Load config
    cfg = load_sdg_config()
    paths = resolve_paths(cfg)
    out_base = paths["generated_scenarios_dir"]

    # Build context
    context = build_kb_context(failure_mode, instance_class)

    # Stage 1: Planning
    narrative = stage1_planning(failure_mode, instance_class, difficulty, context)

    # Stage 2: Spec generation
    spec = stage2_spec_generation(failure_mode, instance_class, difficulty, narrative, context)

    # Stage 4: Render metrics
    print("  Stage 4: Rendering metrics...")
    cloudwatch_metrics = render_spec_metrics(spec)

    # Stage 6: Answer key
    answer = stage6_answer_key(spec)
    spec["answer"] = answer

    # Build remaining fixtures
    print("  Building remaining fixtures...")
    scenario_yml = build_scenario_yml(spec)
    alert_json = build_alert_json(spec)
    rds_events_json = build_rds_events_json(spec)
    pi_json = build_performance_insights_json(spec)

    # Write output
    scenario_id = spec.get("scenario_id", "015-sdg-generated")
    out_dir = out_base / scenario_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "scenario.yml").write_text(yaml.dump(scenario_yml, sort_keys=False, default_flow_style=False))
    (out_dir / "answer.yml").write_text(yaml.dump(spec.get("answer", {}), sort_keys=False, default_flow_style=False))
    (out_dir / "alert.json").write_text(json.dumps(alert_json, indent=2))
    (out_dir / "cloudwatch_metrics.json").write_text(json.dumps(cloudwatch_metrics, indent=2))
    (out_dir / "rds_events.json").write_text(json.dumps(rds_events_json, indent=2))
    (out_dir / "performance_insights.json").write_text(json.dumps(pi_json, indent=2))

    print(f"\n✅ Generated scenario written to:\n   {out_dir}\n")
    print("   Fixture files:")
    for fname in ["scenario.yml", "answer.yml", "alert.json", "cloudwatch_metrics.json", "rds_events.json", "performance_insights.json"]:
        fpath = out_dir / fname
        size = fpath.stat().st_size
        print(f"     - {fname} ({size} bytes)")

    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SDG pipeline to generate 1 RDS scenario.")
    parser.add_argument("--failure_mode", required=True, help="Failure mode (e.g., cpu_saturation)")
    parser.add_argument("--instance_class", default="db.r6g.2xlarge", help="Instance class")
    parser.add_argument("--difficulty", type=int, default=2, help="Difficulty (1-4)")
    args = parser.parse_args()

    try:
        run_pipeline(args.failure_mode, args.instance_class, args.difficulty)
    except KeyboardInterrupt:
        print("\n✋ Interrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
