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

Backups are named `warehouse-YYYYMMDD-HHMMSS.duckdb`. Pick the timestamp
you want to restore to.

### Step 4: Restore with the guarded restore script

Use `openstock-restore-warehouse` rather than a manual `cp`. It performs the
full safe sequence under the exclusive writer lock:

1. verifies the chosen backup **before** touching the live warehouse;
2. takes a `pre-restore-*.duckdb` snapshot of the current warehouse;
3. replaces the warehouse atomically;
4. verifies the restored warehouse and rolls back to the pre-restore snapshot
   if verification fails.

```bash
# Restore a specific backup:
sudo openstock-restore-warehouse --backup \
     /var/lib/openstock/warehouse/backups/warehouse-<timestamp>.duckdb --yes

# Or restore the most recent backup:
sudo openstock-restore-warehouse --latest --yes
```

Because you stopped all services above, the writer lock is free and the restore
proceeds immediately. If a writer is somehow still active, pass
`--wait SECONDS` to block for it, or stop the services first. A failed restore
always leaves a usable warehouse in place.

### Step 5: Restart the platform

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
