# Stage 2 — Structured spec (YAML)

Transform the narrative + RETRIEVED_CONTEXT into a single YAML document that matches the scenario spec schema.

## Rules

- LLM specifies shape and parameters only; no raw float arrays for metrics.
- Patterns must be one of: `ramp_then_flat`, `blip`, `jittered`, `flat_then_collapse`.
- Every metric signal needs: `metric`, `role` (primary_signal | confounder | baseline | red_herring), `pattern`, and pattern-specific numeric fields.
- `time_window_minutes` must cover all `log_lines[].at_min` and `rds_events[].at_min`.
- `answer.required_keywords` must appear verbatim (case-insensitive) in log_lines or rds_events message/detail text.
- `instance_class` must match a key in instance_profiles in context.

## Metric Signal Field Names (EXACT)

### ramp_then_flat pattern
```
pattern: ramp_then_flat
base_value: <float>          # starting value (e.g., 22.0 for CPU%)
peak_value: <float>          # max value reached (e.g., 91.0 for CPU%)
ramp_start_min: <int>        # minute when ramp begins (e.g., 0)
ramp_end_min: <int>          # minute when plateau begins (e.g., 5)
noise_frac: <float>          # jitter amount (default 0.05)
```

### blip pattern
```
pattern: blip
baseline: <float>            # normal baseline value
peak: <float>                # peak during blip
blip_start_min: <int>        # when blip starts
blip_end_min: <int>          # when blip ends
noise_frac: <float>          # jitter amount (default 0.08)
```

### jittered pattern
```
pattern: jittered
mean: <float>                # average value
noise_frac: <float>          # jitter amount (default 0.10)
floor: <float>               # minimum (optional)
ceil: <float>                # maximum (optional)
```

### flat_then_collapse pattern
```
pattern: flat_then_collapse
start_value: <float>         # initial flat value
end_value: <float>           # final collapsed value
collapse_start_min: <int>    # when collapse begins
noise_frac: <float>          # jitter amount (default 0.02)
round_to: <int>              # decimal places (default 0)
```

## Example Spec (cpu_saturation scenario)

```yaml
scenario_id: "015-deadlock-cascade"
failure_mode: cpu_saturation
instance_class: db.r6g.2xlarge
region: us-east-1
difficulty: 2
time_window_minutes: 20
start_time: "2026-04-01T14:00:00Z"
cause: "deadlock cascade from competing UPDATE statements"
adversarial_signals: ["DatabaseConnections"]

metric_signals:
  - metric: CPUUtilization
    role: primary_signal
    pattern: ramp_then_flat
    base_value: 22.0
    peak_value: 91.0
    ramp_start_min: 1
    ramp_end_min: 5
    noise_frac: 0.05

  - metric: DatabaseConnections
    role: confounder
    pattern: blip
    baseline: 180.0
    peak: 310.0
    blip_start_min: 2
    blip_end_min: 8
    noise_frac: 0.08

  - metric: ReadLatency
    role: baseline
    pattern: jittered
    mean: 1.1
    noise_frac: 0.15

log_lines:
  - at_min: 1
    severity: ERROR
    message: "deadlock detected"
    detail: "Process 23891 waits for ShareLock on transaction 7821; blocked by process 23904."
  - at_min: 3
    severity: LOG
    message: "duration: 38291.442 ms  statement: UPDATE orders SET status = 'processed' WHERE batch_id = $1"

rds_events:
  - at_min: 0
    message: "CPU utilization is 91.3% — exceeds threshold of 90%"
    source_identifier: "payments-prod"
    source_type: "db-instance"
    event_categories: ["notification"]

answer:
  root_cause_category: cpu_saturation
  required_keywords: ["deadlock", "CPU", "lock contention"]
  forbidden_categories: ["connection_exhaustion"]
  model_response: "Root cause is CPU saturation due to deadlock cascade..."
```

## Output Format

Emit ONLY the YAML body (no markdown code fences, no extra commentary). The YAML will be parsed directly.
