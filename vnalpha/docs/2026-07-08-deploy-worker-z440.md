# Deployment Report — worker-z440 — 2026-07-08

## Summary

| Item | Value |
|------|-------|
| Date | 2026-07-08 |
| Host | beou@10.113.213.9 (HP-Z440) |
| Status | **SUCCESS (PARTIAL — vnstock-service no update needed)** |

---

## Components Deployed

### 1. vnalpha 0.1.0

**Action**: Updated wheel deployed (new build with 871 tests passing).

**Local build:**
```
make test-vnalpha → 871 passed, 62 skipped
python -m build --wheel --no-isolation → vnalpha-0.1.0-py3-none-any.whl (134KB)
```

**Transfer:**
```
scp vnalpha/dist/vnalpha-0.1.0-py3-none-any.whl beou@10.113.213.9:/tmp/
```

**Remote install:**
```
pip install /tmp/vnalpha-0.1.0-py3-none-any.whl --force-reinstall
  → Successfully installed vnalpha-0.1.0
```

**Smoke test:**
```
vnalpha --help         → Usage: vnalpha [OPTIONS] COMMAND [ARGS]...
pip show vnalpha       → Version: 0.1.0
~/.local/share/vnalpha/warehouse.duckdb → 4.3MB (intact)
```

### 2. vnstock-service

**Action**: No update deployed — **existing image is correct**.

**Reason**: 
- Local build tag `20260707.2221` was identical image ID (`260a5b529f3a`) to running `20260707.0707`
- vnstock code has not changed since last deploy (last commit: `d12057a docs: add vnstock deploy worker note` — docs only)
- Running container verified healthy: `{"status": "ok", "service": "vnstock"}`
- vnstock version in container: 4.0.4 = current codebase

**Registry push attempt (informational):**
- Tried to push `20260707.2221` tag to `docker.x51.vn`
- 9/10 layers: `Layer already exists`
- Layer `8442f6d97711` (288MB pip-install layer): upload timed out repeatedly at ~64KB/s upstream bandwidth
- **Not blocking**: service is healthy, no code changes to deploy

---

## Final State — worker-z440

```
vnstock-service: Up 23 hours (healthy)
  Image:   docker.x51.vn/vnstock/vnstock-service:20260707.0707
  Health:  {"status": "ok", "service": "vnstock"}
  Port:    127.0.0.1:6900

vnalpha:
  Version: 0.1.0
  Venv:    ~/.local/share/vnalpha-venv/
  Launcher: ~/.local/bin/vnalpha
  Warehouse: ~/.local/share/vnalpha/warehouse.duckdb (4.3MB)
```

---

## Notes

### Registry push blocker (tracked issue)
Layer `8442f6d97711` (288MB Python pip-install layer) is missing from `docker.x51.vn/vnstock/vnstock-service`. All other layers are present. Upload from local machine fails due to ~64KB/s upstream bandwidth ceiling (would require ~75 minutes for one layer, times out).

**Workaround for future pushes**: Push from worker-z440 directly (LAN speed). Workflow:
1. `docker save <image> | gzip > /tmp/image.tar.gz` on local
2. `rsync` or `scp` to remote (slow but unattended)
3. `docker load < /tmp/image.tar.gz` on remote
4. `docker tag` + `docker push` from remote (LAN speed)

Alternatively: build image on remote once PyPI/GitHub access is restored, or set up Nexus as a proper pypi cache accessible from the remote.
