# Stage 3 — Postgres logs and RDS-style events

Given the YAML spec, produce:

1. postgres-oriented log lines (severity, message, optional detail) at spec times.
2. rds_events-style notifications consistent with the narrative.

Use RETRIEVED_CONTEXT log templates as syntactic and stylistic anchors; paraphrase with different table names, PIDs, and durations when needed.

Output as JSON with keys `log_lines` and `rds_events` matching the spec's field names (`at_min`, `message`, etc.).
