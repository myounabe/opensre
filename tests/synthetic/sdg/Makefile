# Synthetic data generation (SDG): install embedding deps, build Nomic index, test, smoke retrieval.
#
# From repo root (recommended):
#   make sdg-pipeline
# Or from this directory:
#   make pipeline

# Use `make -C tests/synthetic/sdg` (or `cd` here first) so CURDIR is this folder.
# abspath() splits on spaces — use the shell so repo roots with spaces work.
REPO_ROOT := $(shell cd "$(CURDIR)/../../.." && pwd)

# Python interpreter for recipes (always quoted as "$(PY)" in shell lines).
PY := $(shell if test -x "$(REPO_ROOT)/.venv/bin/python"; then printf '%s' "$(REPO_ROOT)/.venv/bin/python"; else command -v python3; fi)

# Path relative to REPO_ROOT (build_index and smoke run after cd $(REPO_ROOT))
SDG_CONFIG ?= tests/synthetic/sdg/sdg_config.yml

.PHONY: help pipeline sdg-install sdg-index sdg-test sdg-smoke

help:
	@echo "SDG — synthetic data generation / RAG index"
	@echo ""
	@echo "  make pipeline      One shot: install [sdg] → build index → pytest → retrieve smoke"
	@echo "  make sdg-install   pip install -e '.[sdg]' (sentence-transformers + Nomic)"
	@echo "  make sdg-index     Build tests/synthetic/sdg/knowledge_base/vector_index.npz"
	@echo "  make sdg-test      pytest tests/synthetic/sdg/"
	@echo "  make sdg-smoke     One retrieval call (needs sdg-index first)"
	@echo ""
	@echo "Variables: SDG_CONFIG (default $(SDG_CONFIG)), PIP_INSTALL_FLAGS"
	@echo "Repo root (resolved): $(REPO_ROOT)"

# Full pipeline (network on first pip / first model download)
pipeline: sdg-install sdg-index sdg-test sdg-smoke
	@echo "SDG pipeline finished OK."

sdg-install:
	cd "$(REPO_ROOT)" && "$(PY)" -m pip install $(PIP_INSTALL_FLAGS) -e ".[sdg]"

sdg-index:
	cd "$(REPO_ROOT)" && "$(PY)" tests/synthetic/sdg/knowledge_base/build_index.py --config $(SDG_CONFIG)

sdg-test:
	cd "$(REPO_ROOT)" && "$(PY)" -m pytest tests/synthetic/sdg/ -q

sdg-smoke:
	cd "$(REPO_ROOT)" && "$(PY)" -c "from pathlib import Path; from tests.synthetic.sdg.retrieve import retrieve; r = retrieve('RDS PostgreSQL replication lag', config_path=Path(r'$(SDG_CONFIG)')); assert r.texts, 'no chunks retrieved'"
