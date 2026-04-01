# Synthetic data generation (SDG)

This folder holds a **RAG-grounded pipeline** for generating RDS PostgreSQL incident scenarios: the **reference corpus** is the entire **`tests/synthetic/rds_postgres`** tree (scenario dirs, `shared/`, `asset.yml`, etc.); chunks are embedded with **Nomic** (`nomic-ai/nomic-embed-text-v1`). Structured specs are rendered with Python using the same primitives as `tests/synthetic/rds_postgres/shared/generate_fixtures.py`. LLM stages (planning, specs, logs, answer keys) are intended to run via your Anthropic API—prompts live under `prompts/`.

**Generated outputs** mirror the hand-authored layout under **`generated/`** (see `generated/README.md`): each scenario is a folder with the same filenames as `rds_postgres/NNN-slug/` (`scenario.yml`, `answer.yml`, `alert.json`, `cloudwatch_metrics.json`, `rds_events.json`, `performance_insights.json`). Git only keeps `generated/README.md`; scenario dirs are ignored until you commit them explicitly.

## Prerequisites

- Python **3.11+** (matches the repo).
- Optional embedding stack (needed to build the vector index and run diversity embedding checks):

  ```bash
  pip install 'opensre[sdg]'
  ```

  This pulls `sentence-transformers` (and PyTorch). The Nomic weights download on first embed.

## Configuration

Edit **`sdg_config.yml`** in this directory:

| Section | Purpose |
|--------|---------|
| `paths` | Repo, **`rds_fixtures_dir`** (whole suite used as corpus + structural reference), `sdg_knowledge_base_dir`, `vector_index_file`, **`generated_scenarios_dir`**, optional JSONL chunk export |
| `corpus` | Optional **`sdg/knowledge_base/`** supplement; **digest** `cloudwatch_metrics.json` for RAG; per-file chunk size overrides |
| `embedding` | `model_id` for Nomic |
| `chunking` | Default chunk sizes (shared with `corpus` when overrides are null); **fixtures** subtreesettings feed `fixture_chunks.scenario_to_document` / tests |
| `rag` | `retrieval_top_k`, `min_similarity`, reranker placeholder |
| `generation` | Batch size, defaults, retry limits (for future orchestration) |
| `diversity` | Cosine reject threshold vs existing scenarios |
| `logging` | `verbose` for index build |

Paths can be `null`; they resolve relative to the **open-sre-agent repo root** via `config.resolve_paths()`.

### RAG corpus behavior

- **`rds_postgres_corpus.py`** walks **`paths.rds_fixtures_dir`** and indexes `.yml`, `.yaml`, `.json`, `.md`, `.sh`. Python (`scenario_loader.py`, tests, etc.) is skipped.
- **`cloudwatch_metrics.json`** is embedded as a **digest** (metric names, dimensions, min/max/last per series) unless you set `corpus.digest_cloudwatch_metrics: false`.
- If **`corpus.include_sdg_knowledge_base_supplement`** is `true` (default), chunks from `sdg/knowledge_base/` (metric behavior notes, `instance_profiles.yml`, `postgres_log_templates.yml`) are **added** on top of the suite—set to `false` for a corpus drawn **only** from `rds_postgres`.

## One-shot pipeline (Make)

From the **repo root** (installs `opensre[sdg]`, builds the Nomic index, runs `pytest tests/synthetic/sdg/`, then one retrieval smoke test; needs network for pip and first model download):

```bash
make sdg-pipeline
```

From **`tests/synthetic/sdg/`**:

```bash
make pipeline
```

Targets are listed in `make -C tests/synthetic/sdg help`. Override config with `SDG_CONFIG=tests/synthetic/sdg/sdg_config.yml` (path relative to repo root).

## Build the vector index

From the **repo root**:

```bash
python tests/synthetic/sdg/knowledge_base/build_index.py
```

With a custom config:

```bash
python tests/synthetic/sdg/knowledge_base/build_index.py --config /path/to/sdg_config.yml
```

This builds chunks from the **full RDS synthetic suite** (plus optional SDG KB supplement), embeds them with Nomic, and writes **`vector_index.npz`** (default: `knowledge_base/vector_index.npz`, gitignored).

Optional: set `paths.chunk_manifest_export` in YAML to a relative path (e.g. `tests/synthetic/sdg/knowledge_base/chunks.jsonl`) to dump `{ "source", "text" }` per line for inspection.

## Generated scenario output

- Default directory: **`tests/synthetic/sdg/generated/`** (override with `paths.generated_scenarios_dir`).
- Use **`pipeline.generated_scenario_dir(scenario_id)`** or **`write_fixture_preview(spec)`** to write under that root; extend the pipeline until each run emits the full six-file set matching **`rds_postgres`**.

## Retrieve context (RAG)

After the index exists:

```python
from pathlib import Path

from tests.synthetic.sdg.retrieve import format_context_block, retrieve

result = retrieve(
    "replication lag on db.r6g.4xlarge with WAL-heavy workload",
    config_path=Path("tests/synthetic/sdg/sdg_config.yml"),  # optional; defaults to this file
)
context = format_context_block(result)
# Inject `context` into your LLM system prompt or tool messages.
```

`retrieve()` uses **cosine similarity** on L2-normalized Nomic vectors. If you set `rag.reranker.enabled: true` in YAML, retrieval will raise until a cross-encoder is implemented—**keep it `false`** for the current corpus size.

## Other modules

| Module | Role |
|--------|------|
| `rds_postgres_corpus.py` | Walk the full **`rds_postgres`** tree and emit chunk pairs for the index |
| `fixture_chunks.py` | Scenario-card text builder (used in tests / optional tooling) |
| `config.py` | `load_sdg_config()`, `resolve_paths()` |
| `embeddings.py` | Nomic encode with `search_document:` / `search_query:` prefixes |
| `renderer.py` | Spec → CloudWatch-style series (`ramp_then_flat`, `blip`, etc.) |
| `validator.py` | `SpecValidator`: profiles, primary signal, windows, keyword grounding |
| `diversity.py` | Coverage matrix + embedding similarity vs a bank |
| `pipeline.py` | `generated_scenario_dir`, `write_fixture_preview`, metrics/stub orchestration |
| `prompts/` | Markdown prompts for planning, spec, logs, answer key |

## Tests

No GPU required for unit tests:

```bash
python -m pytest tests/synthetic/sdg/ -q
```

## Lint / types (repo-wide)

From repo root, per `AGENTS.md`:

```bash
make lint
make typecheck
make test-cov
```
