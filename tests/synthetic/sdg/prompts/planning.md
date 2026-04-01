# Stage 1 — Scenario planning

You write a short causal narrative for an RDS PostgreSQL incident. Ground every claim in the RETRIEVED_CONTEXT; if context is missing, say what is unknown rather than inventing numbers.

Inputs:

- failure_mode (controlled vocabulary: replication_lag, connection_exhaustion, storage_full, cpu_saturation, failover, healthy)
- instance_class
- difficulty (0–3)
- RETRIEVED_CONTEXT (metric behavior notes, instance limits, log templates)

Output:

- 3–8 paragraphs: timeline, suspected root cause chain, confounders, what an SRE would check first.

Do not emit YAML. Do not emit raw metric time series.
