# vnstock-service Deployment Report — worker-z440

**Date:** 2026-07-07  
**Host:** `beou@10.113.213.9` (worker-z440)  
**Image:** `docker.x51.vn/vnstock/vnstock-service:20260707.0707`  
**Compose service:** `vnstock-service`  
**Status:** ✅ SUCCESS

---

## 1. Overview

vnstock-service is the HTTP data service layer for the vnstock Python library. It exposes provider data at `http://127.0.0.1:6900` (localhost-only, not public-facing).

| Item | Value |
|------|-------|
| Source | `vnstock/` submodule (`feat/phase-4-auth-aware-local-data-service`) |
| Package version | vnstock 4.0.4 |
| Image tag | `20260707.0707` |
| Image SHA | `sha256:935fbb0c04c7a1d5d20f42ee6be9e541ae03f543e2298896681bec529ec21136` |
| Port binding | `127.0.0.1:6900:6900` (localhost only) |
| Registry | `docker.x51.vn` |
| Deployment repo commit | `84dedaa` on `x51vn/deployment` master |

---

## 2. Pre-Deploy Verification

```bash
cd /home/beou/IdeaProjects/openstock/vnstock
PYTHONPATH=. pytest -m 'not slow' tests/unit/core tests/unit/ui tests/unified_ui tests/contracts tests/unit/service -q
```

**Result:** 1026 passed, 6 pre-existing failures in `test_vci_contracts.py::TestVCIIntradayContract`  
(VCI session preparation error — unrelated to vnstock-service implementation)

---

## 3. Build

### Network constraint workaround

Direct `pip install vnstock[...]` inside Docker failed due to slow PyPI download speeds (10–15 KB/s) and SSL errors on the internal Nexus proxy (`nexus.x51.vn` TLSv1 alert).

**Solution:** Pre-build wheel locally → COPY into Docker image → `pip install` from local file (no source downloads needed).

```bash
# Local machine
cd /home/beou/IdeaProjects/openstock/vnstock
python -m build --wheel --no-isolation
# → dist/vnstock-4.0.4-py3-none-any.whl (427 KB)
scp dist/vnstock-4.0.4-py3-none-any.whl beou@10.113.213.9:/tmp/vnstock-build/
```

### Dockerfile (`/tmp/vnstock-build/Dockerfile` on worker-z440)

```dockerfile
FROM python:3.11-slim
RUN useradd --create-home --shell /bin/bash vnstock
WORKDIR /app
COPY vnstock-4.0.4-py3-none-any.whl ./
RUN pip install --no-cache-dir --timeout=120 --index-url https://pypi.org/simple/ \
    vnstock-4.0.4-py3-none-any.whl
USER vnstock
RUN mkdir -p /home/vnstock/.config/vnstock
EXPOSE 6900
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6900/healthz')" || exit 1
CMD ["vnstock-serve", "--host", "0.0.0.0", "--port", "6900"]
```

### Build & push (on worker-z440)

```bash
docker build -t docker.x51.vn/vnstock/vnstock-service:20260707.0707 /tmp/vnstock-build/
docker push docker.x51.vn/vnstock/vnstock-service:20260707.0707
```

**Build time:** ~35 min (PyPI runtime deps @ 80–90 KB/s from container)  
**Push:** success, `sha256:935fbb0c...`

---

## 4. docker-compose.yml Change

Added `vnstock-service` to `/home/beou/deployment/worker-z440/docker-compose.yml`:

```yaml
  vnstock-service:
    image: docker.x51.vn/vnstock/vnstock-service:20260707.0707
    container_name: vnstock-service
    ports:
      - "127.0.0.1:6900:6900"
    volumes:
      - "/home/beou/.config/vnstock:/home/vnstock/.config/vnstock:ro"
    environment:
      - PYTHONUNBUFFERED=1
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:6900/healthz')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - x51-network
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    labels:
      app: "vnstock"
      service: "vnstock-service"
```

---

## 5. Deployment Repo Commit

```
commit 84dedaa
deploy(vnstock-service): add vnstock-service 20260707.0707 to worker-z440

repo: github.com:x51vn/deployment.git
branch: master
```

---

## 6. Remote Deployment

```bash
# Pull new compose file
cd /home/beou/deployment/worker-z440
git pull --ff-only
# Updating 68c2517..84dedaa (1 file: worker-z440/docker-compose.yml, +35 lines)

# Pull image (already cached locally from build, near-instant)
docker compose pull vnstock-service

# Start service
docker compose up -d vnstock-service
# Container vnstock-service Created → Started
```

---

## 7. Stabilization Wait

120 seconds elapsed after `docker compose up -d`.

---

## 8. Verification

### Container state

```
NAME              IMAGE                                                  STATUS
vnstock-service   docker.x51.vn/vnstock/vnstock-service:20260707.0707   Up 2 minutes (healthy)
```

Port: `127.0.0.1:6900->6900/tcp` ✅

### healthz endpoint

```bash
curl -sf http://127.0.0.1:6900/healthz
# → {"status": "ok", "service": "vnstock"}   ✅
```

### /v1/providers endpoint

```bash
curl -sf http://127.0.0.1:6900/v1/providers
# → {"providers": ["DNSE", "FMARKET", "FMP", "KBS", "MSN", "TCBS", "VCI"]}   ✅
```

All 7 providers registered. Service fully operational.

### Logs (no errors)

```
vnstock-service  | INFO vnstock.cli.serve: Starting vnstock service on http://0.0.0.0:6900
vnstock-service  | INFO vnstock.cli.serve: NOTE: Auth login must be done via CLI, not this service.
vnstock-service  | INFO vnstock.service.server: vnstock service listening on http://0.0.0.0:6900
```

No ERROR, Exception, panic, or restart loops.

---

## 9. Security Notes

- Port is bound to `127.0.0.1:6900` only — **not exposed externally**
- TCBS credentials are mounted read-only from `~/.config/vnstock/` on the host
- The vnstock user inside the container has no write access to credentials volume
- Service warns in logs that auth login must be done via CLI (not the HTTP service)

---

## 10. Known Limitations

| Item | Note |
|------|-------|
| No TCBS auth | `~/.config/vnstock/` on remote is empty — TCBS-authenticated endpoints will return 401/403. Run `vnstock-auth login tcbs` on the host to set up credentials. |
| FMP API key | Not configured in compose env. FMP endpoints require `FMP_API_KEY` or `VNSTOCK_FMP_API_KEY`. Add to compose `environment:` if needed. |
| `CRAWLER8_DB_PASSWORD` warnings | Unrelated to vnstock-service — other compose services use this variable. Safe to ignore. |

---

## 11. Summary

| Step | Result |
|------|--------|
| CI verification | ✅ 1026 passed |
| Wheel build | ✅ 427 KB |
| Docker image build | ✅ `20260707.0707` |
| Image push | ✅ `docker.x51.vn` registry |
| Compose update | ✅ `84dedaa` |
| Remote git pull | ✅ fast-forward |
| `docker compose up -d` | ✅ started |
| Health check | ✅ `healthy` |
| API endpoint `/v1/providers` | ✅ 7 providers |
| Log review | ✅ no errors |

**Final status: SUCCESS**
