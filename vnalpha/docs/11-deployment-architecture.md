# 11. Deployment architecture

> **Status:** current single-host deployment contract.
>
> The canonical runtime topology is defined by the root `docker-compose.yml`,
> `packaging/config/vnalpha.env` and the Debian packaging scripts. Component
> examples must not define competing warehouse paths or model defaults.

## Deployment model

OpenStock separates the Docker-managed data platform from the host-installed
terminal workspace:

```text
Docker
├── vnstock-service       # long-running localhost data service
├── vnstock-login         # optional one-shot credential helper
└── vnalpha-worker        # one-shot pipeline jobs

Host
├── /var/lib/openstock/vnstock-config/
├── /var/lib/openstock/warehouse/warehouse.duckdb
└── vnalpha Debian package → CLI and Textual TUI
```

The TUI is launched by the user from a terminal, SSH session or `tmux`; it is not
a background container or web dashboard.

## Canonical paths

Production defaults:

```bash
OPENSTOCK_WAREHOUSE_DIR=/var/lib/openstock/warehouse
VNSTOCK_CONFIG_DIR=/var/lib/openstock/vnstock-config
VNALPHA_WAREHOUSE_PATH=/var/lib/openstock/warehouse/warehouse.duckdb
```

Prepare them before starting Compose:

```bash
sudo install -d -m 0755 /var/lib/openstock/warehouse
sudo install -d -m 0755 /var/lib/openstock/vnstock-config
```

The root Compose file mounts `OPENSTOCK_WAREHOUSE_DIR` at `/warehouse`; the
worker writes `/warehouse/warehouse.duckdb`. The Debian package reads the same
host file through `VNALPHA_WAREHOUSE_PATH`.

Never hard-code a developer home directory in Compose or packaging. Development
installations may override the two host directories through `.env`, but worker
and TUI must still resolve the same database.

## Components

### `vnstock-service`

Deployment: Docker service bound to `127.0.0.1:6900`.

Responsibilities:

- provider access and authentication policy;
- plugin routing and health;
- canonical data contracts and quality checks;
- bounded read-only HTTP responses;
- safe provider diagnostics.

Commercial providers remain optional. FiinQuantX is built only when
`VNSTOCK_INSTALL_FIINQUANTX=true` and requires separate licensed-runtime and
commercial-policy evidence.

### `vnstock-login`

Deployment: optional one-shot Compose profile with write access to the provider
configuration directory.

```bash
docker compose --profile login run --rm vnstock-login status
```

Credentials remain outside query parameters, logs, artifacts and assistant
inputs.

### `vnalpha-worker`

Deployment: one-shot Docker job using the `vnalpha` CLI.

```bash
docker compose --profile job run --rm vnalpha-worker init
docker compose --profile job run --rm vnalpha-worker sync symbols
docker compose --profile job run --rm vnalpha-worker build canonical
docker compose --profile job run --rm vnalpha-worker build features --date today
docker compose --profile job run --rm vnalpha-worker score --date today
```

The worker is not a daemon. A scheduler or systemd timer may invoke these jobs,
but overlapping writers are prohibited for the DuckDB deployment.

### Host-installed `vnalpha`

Deployment: Debian package under `/opt/vnalpha` with launchers in `/usr/bin`.

```bash
vnalpha --help
vnalpha tui
```

The package loads `/etc/vnalpha/vnalpha.env` and reads the shared warehouse.
Interactive workflows should be read-mostly while a pipeline job is active.

## Root Compose is canonical

Use:

```bash
make up-vnstock
make down-vnstock
make login-vnstock
make validate-compose
```

or the equivalent root commands:

```bash
docker compose up -d vnstock-service
docker compose stop vnstock-service
docker compose config --quiet
```

`vnstock/docker-compose.yml` may be used as a component development fixture, but
it does not define the integrated worker/warehouse topology and must not be used
as the root Makefile deployment source.

## LLM configuration

AI is optional. Deterministic research remains available with no model configured.

```bash
VNALPHA_LLM_ENDPOINT=
VNALPHA_LLM_MODEL=
VNALPHA_LLM_API_KEY=
VNALPHA_LLM_STORE_RAW=false
```

Do not ship a public endpoint, placeholder model or guessed model ID. Configure
`VNALPHA_LLM_ENDPOINT`, `VNALPHA_LLM_MODEL` (or `VNALPHA_MODEL_DEFAULT`) and the
dedicated `VNALPHA_LLM_API_KEY` only after the endpoint and alias are verified.
A process-level `OPENAI_API_KEY` does not enable OpenStock AI. Optional profile
routes may be set individually:

```bash
VNALPHA_MODEL_SMALL=
VNALPHA_MODEL_DEFAULT=
VNALPHA_MODEL_REASONING=
VNALPHA_MODEL_LONG_CONTEXT=
```

When all profiles resolve to one model, status surfaces must report single-model
routing rather than a false fallback chain.

## FiinQuantX persistence

The worker defaults to:

```bash
VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=false
```

An environment acknowledgement is not commercial approval. Enable persistence
only after a reviewed decision covers the actual storage and exposure mode.

## DuckDB concurrency

The current embedded warehouse follows these rules:

1. run only one writer at a time;
2. serialize sync, repair, build, score and outcome jobs;
3. keep TUI operations read-only where practical during jobs;
4. back up the file before migrations or operational repair;
5. do not place the database on an unsafe network filesystem.

Move to a server database only when concurrent writers, multi-user SQL access or
central transaction control become real requirements.

## systemd integration

A systemd unit may manage the root Compose service:

```ini
[Unit]
Description=OpenStock data platform
Requires=docker.service
After=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/openstock
ExecStart=/usr/bin/docker compose up -d vnstock-service
ExecStop=/usr/bin/docker compose stop vnstock-service
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Use separate timer units for daily one-shot worker commands. Do not launch the
interactive TUI from systemd.

## Validation

Before release or deployment:

```bash
make validate-compose
make verify-repo-consistency
make lint-vnalpha
make verify-r0
make test-vnalpha
make verify-vnalpha-package
```

CI must run the relevant lint, tests, package builds and consistency checks on
pull requests. Manual documentation of failures is not a replacement for a merge
gate.
