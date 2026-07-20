# Debian package install and upgrade

The `vnalpha` Debian package is a host-native client and daily research worker.
It does not install Docker Engine, a `vnstock-service` image, credentials or the
external `/opt/openstock` Compose deployment.

## What the package installs

- `/usr/bin/vnalpha` and `/usr/bin/vnalpha-poc`;
- an offline Python virtual environment under `/opt/vnalpha/venv`;
- `openstock-verify`, `openstock-mvp1-start`,
  `openstock-backup-warehouse` and `openstock-restore-warehouse`;
- disabled-by-default daily maintenance systemd units;
- `/etc/vnalpha/vnalpha.env` as a protected conffile;
- the operator documentation under `/usr/share/doc/vnalpha/`.

## Install

```bash
sudo apt install -y ./vnalpha_<version>_amd64.deb
sudo usermod -aG openstock "$USER"
```

Start a new login session after the group change. Then initialize and verify:

```bash
vnalpha init
openstock-verify --mvp1
```

The package does not enable the daily timer. Enable it only after verification:

```bash
sudo systemctl enable --now openstock-daily-pipeline.timer
```

## Upgrade behavior

Upgrades are offline and transactional:

1. a replacement venv is built from the bundled wheelhouse;
2. the exact packaged version is installed with `--no-index`;
3. the replacement CLI must pass a smoke check;
4. only then is the active venv replaced.

A missing or incomplete wheel bundle fails closed. The installer never falls
back to PyPI and never removes the warehouse, knowledge cards or logs.

## Shared state permissions

The installer creates and maintains these paths as `root:openstock`:

- `/var/lib/openstock/warehouse` — mode `0770`;
- `/var/lib/openstock/knowledge` — mode `0770`;
- `/var/log/openstock` — mode `0770`.

The daily service runs as root with primary group `openstock` and `UMask=0007`,
so approved operators and the scheduled writer use the same state contract.

## External prerequisites

Before `openstock-mvp1-start` can start the data service, provide either:

- an already healthy local `vnstock-service` at the configured URL; or
- Docker Compose deployment assets under `OPENSTOCK_HOME`, normally
  `/opt/openstock`.

FiinQuantX and LLM credentials remain disabled and empty by default. The
package never creates, enables or changes commercial approvals automatically.
