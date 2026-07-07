# Rollback Guide

Three rollback levels in order of scope. Start with the narrowest one that
addresses your problem; only go wider if it doesn't resolve the issue.

---

## Level 1: Rollback the vnalpha Debian package (task 7.5)

Use this when a new `vnalpha.deb` breaks the TUI or CLI commands.

### Find the previous package

If you kept the old `.deb` file:

```bash
ls ~/packages/vnalpha_*.deb
```

If you need to retrieve it from your build artifacts or CI store, download it
before proceeding.

### Downgrade

```bash
sudo dpkg -i ./vnalpha_<prev-version>_amd64.deb
```

`dpkg -i` on a lower version number downgrades in place. It overwrites the
launcher scripts (`/usr/bin/vnalpha`, `/usr/bin/vnalpha-poc`) and the venv
at `/opt/vnalpha/venv/` without touching the warehouse.

### Verify the downgrade

```bash
vnalpha --version
openstock-verify
```

The config file at `/etc/vnalpha/vnalpha.env` is not touched by the package
upgrade or downgrade. If you need to restore it:

```bash
sudo cp /etc/vnalpha/vnalpha.env.dpkg-old /etc/vnalpha/vnalpha.env
```

---

## Level 2: Rollback Docker data platform images (task 7.6)

Use this when a new container image for `vnstock-service` introduces a regression.

### Pin the previous image tag in the compose file

Open `/opt/openstock/docker-compose.yml` and change the `image:` line for
`vnstock-service` to the last known-good tag:

```yaml
services:
  vnstock-service:
    image: ghcr.io/thinh-vu/vnstock:2025.07.01   # pinned to previous
```

### Pull the pinned image and restart

```bash
cd /opt/openstock
sudo docker compose pull vnstock-service
sudo systemctl restart openstock-data-platform
```

### Verify

```bash
sudo systemctl status openstock-data-platform
openstock-verify
```

Once you've confirmed the rollback is stable, keep the pinned tag in the
compose file until a fixed image is available.

---

## Level 3: Restore the DuckDB warehouse from backup (task 7.7)

Use this when the warehouse file is corrupted or contains bad data from a
pipeline run.

**This procedure is destructive.** The current warehouse is replaced by the
backup. Stop all writers first.

### Step 1: Stop scheduled jobs

Disable and stop the daily pipeline timer so no job runs during the restore:

```bash
sudo systemctl stop openstock-daily-pipeline.timer
sudo systemctl stop openstock-daily-pipeline.service
```

### Step 2: Stop the data platform

```bash
sudo systemctl stop openstock-data-platform
```

This shuts down the `vnstock-service` container and ensures no Docker-side
process holds the warehouse open.

### Step 3: List available backups

```bash
ls -lht /var/lib/openstock/warehouse/backups/
```

Backups are named `warehouse_YYYYMMDD_HHMMSS.duckdb`. Pick the timestamp
you want to restore to.

### Step 4: Back up the current (broken) warehouse first

Before overwriting, preserve the current file in case you need it for
diagnosis:

```bash
sudo cp /var/lib/openstock/warehouse/warehouse.duckdb \
        /var/lib/openstock/warehouse/warehouse.duckdb.pre-restore
```

### Step 5: Take a fresh backup with the flock guard

The `openstock-backup-warehouse` script uses `flock` to prevent running
while a writer job holds the lock. If a job is somehow still running, the
script will wait or fail rather than producing a corrupt backup. Because you
stopped all services above, the lock is free:

```bash
sudo openstock-backup-warehouse
```

If you want to skip the age check and force a fresh backup regardless of
when the last one was taken, pass `--force`:

```bash
sudo openstock-backup-warehouse --force
```

### Step 6: Copy the chosen backup into place

```bash
sudo cp /var/lib/openstock/warehouse/backups/warehouse_<timestamp>.duckdb \
        /var/lib/openstock/warehouse/warehouse.duckdb
```

### Step 7: Restart the platform

```bash
sudo systemctl start openstock-data-platform
```

Re-enable the timer only after verification passes:

```bash
sudo systemctl enable --now openstock-daily-pipeline.timer
```

---

## Post-restore: Run openstock-verify (task 7.8)

After any rollback or restore, `openstock-verify` **must pass** before the
platform is considered healthy. This confirms the service is up, the health
endpoint responds, the warehouse file exists, and all safety boundaries are
intact.

```bash
openstock-verify
```

Expected output ends with:

```
Status: PASS
```

If any `[FAIL]` lines appear, address them before re-enabling scheduled jobs
or letting users access the TUI.

To re-initialize the warehouse schema after a restore from an older backup
(e.g., the schema has changed since the backup was taken):

```bash
openstock-verify --init
```

This runs `vnalpha init` via the worker container and is safe to run
idempotently on an existing warehouse.
