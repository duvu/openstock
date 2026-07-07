# vnalpha Worker Image
#
# Provides the `vnalpha` CLI for pipeline job execution inside Docker.
# This image is NOT a long-running service — it is invoked via
# `docker compose run --rm vnalpha-worker <command>` with profiles: [job].
#
# Research-only: no broker execution, no order/account APIs.
#
# Build (from openstock root via compose):
#   docker compose build vnalpha-worker
#
# Run examples:
#   docker compose run --rm vnalpha-worker init
#   docker compose run --rm vnalpha-worker sync symbols
#   docker compose run --rm vnalpha-worker sync ohlcv --universe VN30
#   docker compose run --rm vnalpha-worker build canonical
#   docker compose run --rm vnalpha-worker build features
#   docker compose run --rm vnalpha-worker score
#   docker compose run --rm vnalpha-worker watchlist
#   docker compose run --rm vnalpha-worker outcome evaluate --date 2024-01-15
#
# Expected mounts and environment (set by docker-compose.yml):
#   /warehouse                         — DuckDB warehouse directory (bind mount)
#   VNSTOCK_SERVICE_URL                — http://vnstock-service:6900
#   VNALPHA_WAREHOUSE_PATH             — /warehouse/warehouse.duckdb

FROM python:3.11-slim

# Non-root user for security, consistent with vnstock image
RUN useradd --create-home --shell /bin/bash vnalpha

WORKDIR /app

# Install build tooling in one layer, then remove in same RUN to keep image lean
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy package manifest first for better layer caching
COPY pyproject.toml ./
COPY src/ ./src/

# Install vnalpha and all runtime dependencies
RUN pip install --no-cache-dir .

# Warehouse directory (bind-mounted at runtime from /var/lib/openstock/warehouse)
RUN mkdir -p /warehouse && chown vnalpha:vnalpha /warehouse

# Switch to non-root user
USER vnalpha

# Entrypoint: all container args are forwarded to the vnalpha CLI
# Usage: docker compose run --rm vnalpha-worker <subcommand> [options]
ENTRYPOINT ["vnalpha"]

# Default: show help (no-op for pipeline jobs, useful for smoke-test)
CMD ["--help"]
