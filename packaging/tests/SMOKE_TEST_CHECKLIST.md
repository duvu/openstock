# Smoke Test Checklist — Fresh VM

Manual checklist for validating the full openstock stack on a fresh Debian/Ubuntu VM.
Run each step in order. Tick the box when the expected output is observed.

> **Target OS**: Debian 12 (Bookworm) or Ubuntu 22.04/24.04 LTS  
> **Architecture**: amd64  
> **Prerequisites**: A user with `sudo` access and internet connectivity.

---

## 1. Prerequisites

- [ ] **Install Docker Engine**

  ```bash
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER"
  newgrp docker
  ```

  **Expected**: `docker --version` prints `Docker version 24.x` or newer.

- [ ] **Verify Docker Compose plugin**

  ```bash
  docker compose version
  ```

  **Expected**: `Docker Compose version v2.x.x` or newer.

- [ ] **Install shellcheck (optional — for CI linting)**

  ```bash
  sudo apt-get install -y shellcheck
  shellcheck --version
  ```

  **Expected**: `version: 0.x.x`.

- [ ] **Clone the repository**

  ```bash
  git clone https://github.com/your-org/openstock.git /opt/openstock
  cd /opt/openstock
  ```

  **Expected**: Repository cloned, `ls packaging/` shows `scripts/`, `systemd/`, `build-deb.sh`, etc.

---

## 2. Install Debian Package (task 9.6)

> **Requires a Debian 12 container or the host VM itself.**  
> This step validates that the `.deb` installs cleanly and exposes the `vnalpha` command.

- [ ] **Build the Debian package** (skip if you have a pre-built `.deb`)

  ```bash
  cd /opt/openstock
  bash packaging/build-deb.sh
  ```

  **Expected**: `packaging/dist/vnalpha_*.deb` is created with no errors.

- [ ] **Validate install in a Debian 12 container**

  ```bash
  DEB_FILE="$(ls /opt/openstock/packaging/dist/vnalpha_*.deb | head -1)"
  docker run --rm -it \
    -v "$DEB_FILE:/tmp/vnalpha.deb:ro" \
    debian:12 bash -c "
      apt-get update -qq &&
      apt-get install -y --no-install-recommends /tmp/vnalpha.deb &&
      vnalpha --version &&
      vnalpha --help | head -5
    "
  ```

  **Expected**: Package installs without errors; `vnalpha --version` prints a version string; `vnalpha --help` shows usage.

- [ ] **Validate on the host VM directly** (if Debian 12)

  ```bash
  sudo apt-get install -y "$(ls packaging/dist/vnalpha_*.deb | head -1)"
  vnalpha --version
  which vnalpha   # should print /usr/bin/vnalpha
  ```

  **Expected**: `vnalpha` is on `$PATH` at `/usr/bin/vnalpha`.

---

## 3. Start the Data Platform

- [ ] **Copy and edit the environment file** (optional — defaults are fine for first install)

  ```bash
  sudo mkdir -p /etc/openstock
  sudo cp packaging/config/openstock.env.example /etc/openstock/openstock.env
  sudo nano /etc/openstock/openstock.env   # review defaults
  ```

  **Expected**: File exists at `/etc/openstock/openstock.env`.

- [ ] **Install and enable the systemd service**

  ```bash
  sudo cp packaging/systemd/openstock-data-platform.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable openstock-data-platform
  sudo systemctl start openstock-data-platform
  ```

  **Expected**: `systemctl status openstock-data-platform` shows `active (running)`.

- [ ] **Verify containers are up**

  ```bash
  docker compose ps
  ```

  **Expected**: `vnstock-service` is listed as `running` or `Up`.

---

## 4. Verify the Platform

- [ ] **Run the verification script**

  ```bash
  bash packaging/scripts/openstock-verify
  ```

  **Expected output** (all lines):
  ```
  [OK]   docker binary found: Docker version ...
  [OK]   docker compose (plugin V2) found: ...
  [OK]   openstock-data-platform systemd service is active
  [OK]   vnstock-service container is running
  [OK]   vnstock-service healthz returned HTTP 200 (http://127.0.0.1:6900/healthz)
  [OK]   forbidden endpoint /v1/order returns 404 (safety boundary OK)
  [OK]   forbidden endpoint /v1/account returns 404 (safety boundary OK)
  [OK]   forbidden endpoint /v1/portfolio returns 404 (safety boundary OK)
  [OK]   forbidden endpoint /v1/trading returns 404 (safety boundary OK)
  Status: PASS
  ```

- [ ] **Run CI-mode verify (no live services needed)**

  ```bash
  bash packaging/scripts/openstock-verify --ci
  echo "Exit code: $?"
  ```

  **Expected**: Exit code `0`; no `[FAIL]` lines in output.

---

## 5. Initial Data Sync

- [ ] **Initialize the warehouse**

  ```bash
  bash packaging/scripts/openstock-verify --init
  ```

  or directly:

  ```bash
  docker compose run --rm vnalpha-worker init
  ```

  **Expected**: `[OK]   warehouse initialized: /var/lib/openstock/warehouse/warehouse.duckdb` (or file already exists).

- [ ] **Confirm warehouse file exists**

  ```bash
  ls -lh /var/lib/openstock/warehouse/warehouse.duckdb
  ```

  **Expected**: File exists and is non-zero in size.

- [ ] **Run a sync for a small demo universe** (requires network access)

  ```bash
  docker compose run --rm vnalpha-worker sync --universe demo
  ```

  **Expected**: Sync completes with no fatal errors; warehouse file size increases.

---

## 6. TUI (Terminal User Interface)

- [ ] **Test non-interactive entrypoint** (`vnalpha tui --help`)

  ```bash
  vnalpha tui --help
  ```

  **Expected**: Help text printed; exits 0.

- [ ] **Launch the TUI interactively** (from a real terminal, not a pipe)

  ```bash
  vnalpha tui
  ```

  **Expected**: TUI opens in the terminal. Press `q` or `Ctrl-C` to exit cleanly.

- [ ] **Test via `vnalpha-poc` launcher** (if installed)

  ```bash
  vnalpha-poc --help
  ```

  **Expected**: Help text printed or TUI launched; no import errors.

---

## 7. Daily Pipeline Timer (optional)

- [ ] **Install and check the timer**

  ```bash
  sudo cp packaging/systemd/openstock-daily-pipeline.service /etc/systemd/system/
  sudo cp packaging/systemd/openstock-daily-pipeline.timer   /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable --now openstock-daily-pipeline.timer
  systemctl list-timers openstock-daily-pipeline.timer
  ```

  **Expected**: Timer listed with next trigger time.

---

## 8. Backup

- [ ] **Run the backup script**

  ```bash
  bash packaging/scripts/openstock-backup-warehouse
  ```

  **Expected**: A timestamped `.duckdb` file created under `/var/lib/openstock/warehouse/backups/`; script exits 0.

- [ ] **Confirm backup exists**

  ```bash
  ls -lh /var/lib/openstock/warehouse/backups/
  ```

  **Expected**: At least one `warehouse_*.duckdb` backup file.

---

## 9. Automated Test Suite

- [ ] **Run shellcheck on all packaging scripts**

  ```bash
  bash packaging/tests/test_shellcheck.sh
  ```

  **Expected**: All scripts pass; output ends with `shellcheck: N OK, 0 FAIL`.

- [ ] **Run helper unit tests**

  ```bash
  bash packaging/tests/test_verify_helpers.sh
  ```

  **Expected**: All TAP lines start with `ok`; summary shows `failed: 0`.

- [ ] **Run compose config and CI verify tests**

  ```bash
  bash packaging/tests/test_compose_config.sh
  ```

  **Expected**: All checks pass; `Results: N OK, 0 FAIL`.

---

## 10. Cleanup

- [ ] **Stop the platform**

  ```bash
  sudo systemctl stop openstock-data-platform
  systemctl status openstock-data-platform
  ```

  **Expected**: Status shows `inactive (dead)`.

- [ ] **Remove installed Debian package** (test uninstall leaves warehouse intact)

  ```bash
  sudo apt-get remove -y vnalpha
  ls /var/lib/openstock/warehouse/warehouse.duckdb
  ```

  **Expected**: Package removed; warehouse file still exists (uninstall must NOT delete user data).

---

## Notes

- **Task 9.6 container validation** requires Docker on the test host. Use
  `docker run --rm -it -v /path/to/vnalpha.deb:/tmp/vnalpha.deb:ro debian:12 bash`
  as documented in §2 above.
- **Live network checks** (sync, healthz) require the `vnstock-service` container running
  and internet access to the upstream data provider.
- **CI-only runs** (no live services): run `bash packaging/scripts/openstock-verify --ci`
  and `bash packaging/tests/test_verify_helpers.sh` — these never require live services.
