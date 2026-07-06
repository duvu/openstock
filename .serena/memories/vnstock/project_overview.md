# vnstock Project Overview

## Purpose
Vietnamese financial market data toolkit (v4) — Python library + local HTTP service.

## Tech Stack
- Python >=3.10
- stdlib http.server for the service layer (no extra deps)
- ruff (linter/formatter), pre-commit, pytest

## Structure
- `vnstock/` — main package
  - `service/` — local HTTP data service (port 6900)
    - `server.py` — VnstockHandler, run_server()
    - `dataset_mapper.py` — path_to_dataset(), MapperError, extract_runtime_params()
    - `serializers.py`, `runtime_dependency.py`
  - `ui/` — Unified UI facade
  - `explorer/` — provider scrapers
  - `core/` — registry, router, cache, quality
- `tests/unit/service/` — existing unit tests for service layer
- `docs/` — existing markdown docs

## Key Commands
- `make verify` — full verification (lint + format + pre-commit + pytest)
- `PYTHONPATH=. pytest tests/unit/service/` — run service unit tests
- `make lint` / `make format`

## Style
- Ruff, line length 88, py310, double quotes, E/W/F/I/B/C4, E501 ignored
