---
metric: ReplicaLag
failure_mode: replication_lag
instance_class: db.r6g.4xlarge
---

## Baseline

baseline_range: 0.4–3.0 seconds

## Fault behavior

fault_behavior: primary signal — climbs monotonically from baseline toward hundreds of seconds under sustained apply lag.

## Causal ordering

causal_order: often lagging — upstream write throughput or WAL generation may spike first (T+0 to T+2 min); ReplicaLag climbs T+2 to T+8 min.

## Confounder risk

confounder_risk: medium — elevated CPU on replica can co-occur; check WAL / apply vs CPU-only noise.

## Notes

On Aurora, ReplicaLag may reset sharply after topology changes rather than a single long plateau.
