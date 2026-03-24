# Local Grafana Live

This path runs Tracer against a real local Grafana instance instead of bundled Grafana evidence.

![Live local Grafana flow](assets/local-grafana-live-flow.gif)

Level 1 scope:

- real local `Grafana`
- real local `Loki`
- real log queries from Tracer into the local Grafana instance
- synthetic alert payload

## Prerequisites

- Docker
- Python 3.11+
- `make`
- `ANTHROPIC_API_KEY` in `.env` or your shell

## Run it

```bash
make local-grafana-live
```

This will:

1. Start a local `Grafana + Loki` stack
2. Seed real failure logs into Loki
3. Query those logs through the current Grafana client
4. Render an RCA report locally

## Stop the stack

```bash
make grafana-local-down
```

## Notes

This is the live local Grafana MVP. It still uses a synthetic alert payload, but the evidence comes from real queries against a local Grafana instance.
