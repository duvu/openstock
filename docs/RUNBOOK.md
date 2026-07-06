# openstock Local Development Runbook

Local research workflow: vnstock-service → vnalpha sync → DuckDB → features → scoring → TUI.

---

## Prerequisites

| Requirement | Minimum version |
|-------------|----------------|
| Python      | 3.10+          |
| Docker      | 24+            |
| pip         | 23+            |

---

## First-time Setup

### 1. Copy environment config

```bash
cp .env.example .env
# Edit .env to adjust paths / ports if needed
```

### 2. Install vnalpha

```bash
make install-vnalpha
# Equivalent: pip install -e vnalpha/
```

### 3. Start vnstock-service

```bash
make up-vnstock
# Equivalent: docker compose -f vnstock/docker-compose.yml up -d
```

Verify the service is healthy:

```bash
curl http://127.0.0.1:6900/healthz
```

Expected response: `{"status": "ok"}` (or similar 200 JSON).

---

## Daily Workflow

Run the pipeline steps in order:

```bash
make sync       # pull symbols + OHLCV, build canonical dataset
make features   # compute features for today
make score      # run scoring model + update watchlist
make tui        # open the interactive TUI
```

Or as a single pipeline:

```bash
make sync && make features && make score && make tui
```

---

## Individual vnalpha Commands

### Sync

```bash
# Sync the symbol universe
vnalpha sync symbols

# Sync OHLCV data for VN30 from a given start date
vnalpha sync ohlcv --universe VN30 --start 2024-01-01

# Build the canonical dataset from raw synced data
vnalpha build canonical
```

### Feature Engineering

```bash
# Build features for today
vnalpha build features --date today

# Build features for a specific date
vnalpha build features --date 2025-06-01
```

### Scoring & Watchlist

```bash
# Score all symbols for today
vnalpha score --date today

# Update watchlist for today
vnalpha watchlist --date today
```

### TUI

```bash
vnalpha tui
```

---

## Service Management

### Start / Stop

```bash
make up-vnstock     # start vnstock-service in background
make down-vnstock   # stop vnstock-service
```

Or using the top-level compose file:

```bash
docker compose up -d
docker compose down
docker compose logs -f
```

### Health Check

```bash
curl http://127.0.0.1:6900/healthz
```

### Provider Capabilities

```bash
curl http://127.0.0.1:6900/v1/providers/capabilities
```

---

## Development

### Lint

```bash
make lint-vnalpha
# Equivalent: cd vnalpha && ruff check . && ruff format --check .
```

### Tests

```bash
make test-vnalpha
# Equivalent: cd vnalpha && pytest -q
```

---

## Quick Reference

```
make help            — list all available targets
make up-vnstock      — start vnstock-service
make down-vnstock    — stop vnstock-service
make install-vnalpha — install vnalpha (editable)
make sync            — sync data + build canonical
make features        — build features for today
make score           — score + update watchlist
make tui             — launch TUI
make lint-vnalpha    — lint vnalpha
make test-vnalpha    — test vnalpha
```
