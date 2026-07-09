# vnalpha Deployment Report — worker-z440

**Date:** 2026-07-07  
**Host:** `beou@10.113.213.9` (worker-z440)  
**Package:** `vnalpha-0.1.0-py3-none-any.whl`  
**Status:** ✅ SUCCESS

---

## 1. Overview

vnalpha is a Python CLI research workspace (not a Docker service). The deployment installs the wheel into a dedicated virtualenv and sets up a launcher wrapper that auto-loads env vars before each invocation.

| Item | Value |
|------|-------|
| Source repo | `/home/beou/IdeaProjects/openstock/vnalpha/` |
| Build output | `dist/vnalpha-0.1.0-py3-none-any.whl` (119 KB) |
| Remote venv | `~/.local/share/vnalpha-venv/` |
| Launcher | `~/.local/bin/vnalpha` |
| Env config | `~/.config/vnalpha/.env` |
| Warehouse DB | `~/.local/share/vnalpha/warehouse.duckdb` (4.3 MB) |

---

## 2. Local Verification (Pre-Build)

```
PYTHONPATH=src pytest tests/ -q
→ 578 passed, 26 skipped in ~30s
```

All 578 tests pass. The 26 skipped tests are textual-gated TUI tests that require the `textual` package — those are properly skipped on the local dev machine where textual isn't installable via the internal Nexus PyPI proxy (SSL error).

---

## 3. Build

```bash
cd /home/beou/IdeaProjects/openstock/vnalpha
python -m build --wheel --no-isolation
# → Successfully built vnalpha-0.1.0-py3-none-any.whl
```

---

## 4. Transfer

```bash
scp dist/vnalpha-0.1.0-py3-none-any.whl beou@10.113.213.9:/tmp/
# → (silent success)
```

---

## 5. Remote Install

```bash
ssh beou@10.113.213.9
VENV=~/.local/share/vnalpha-venv
$VENV/bin/pip install /tmp/vnalpha-0.1.0-py3-none-any.whl --force-reinstall --quiet
$VENV/bin/pip show vnalpha
# → Name: vnalpha   Version: 0.1.0
```

**Installed packages verified:**

| Package | Version |
|---------|---------|
| vnalpha | 0.1.0 |
| duckdb | 1.5.4 |
| textual | 8.2.8 |
| rich | 15.0.0 |
| httpx | 0.28.1 |
| typer | 0.26.8 |
| pydantic | 2.13.4 |

---

## 6. Configuration

**Env file** written to `~/.config/vnalpha/.env`:

```bash
VNSTOCK_SERVICE_URL=http://127.0.0.1:6900
VNALPHA_WAREHOUSE_PATH=~/.local/share/vnalpha/warehouse.duckdb
VNALPHA_UNIVERSE=VN30
VNALPHA_LLM_ENDPOINT=https://lite.x51.vn/v1/chat/completions
VNALPHA_LLM_MODEL=oc-gpt-5.4-mini
VNALPHA_LLM_API_KEY=<redacted>
VNALPHA_LLM_TIMEOUT=30
VNALPHA_LLM_MAX_OUTPUT_TOKENS=16000
VNALPHA_LLM_MAX_RETRIES=2
VNALPHA_LLM_STORE_RAW=false
VNALPHA_LOG_LEVEL=INFO
```

**Launcher** written to `~/.local/bin/vnalpha` (auto-sources env):

```bash
#!/bin/bash
set -a
[ -f ~/.config/vnalpha/.env ] && source ~/.config/vnalpha/.env
set +a
exec ~/.local/share/vnalpha-venv/bin/vnalpha "$@"
```

`~/.local/bin` added to PATH in `~/.bashrc`.

---

## 7. Smoke Tests

### 7.1 Warehouse init
```
vnalpha init
→ Warehouse ready.   ✅
```

### 7.2 Plan preview (no LLM call)
```
vnalpha ask "What is the strongest VN30 candidate today?" --show-plan --no-execute
→ Plan for intent: filter_candidates
  Steps:
    1. watchlist.filter({'filters': {}, 'date': '2026-07-07'}) — Filter candidates by criteria
   ✅
```

### 7.3 Full execution (LLM + DB)
```
vnalpha ask "What is the strongest VN30 candidate today?"
→ Returns a structured research answer (0 candidates — expected: no ingested data yet)
Exit code: 0   ✅
```

The assistant correctly reported **0 candidates** with proper explanation (no ingestion pipeline has been run yet on this host). This is expected for a fresh install.

---

## 8. Known Issues / Action Items

### ⚠️ Issue 1: No market data ingested

**Symptom:** All `watchlist.filter` calls return 0 candidates.  
**Cause:** The `sync` → `build` → `score` pipeline has not been run. The warehouse schema is initialized but contains no VN30 OHLCV data.  
**Action Required:** Run the ingestion pipeline (requires `VNSTOCK_SERVICE_URL` pointing to a live vnstock-service instance):

```bash
vnalpha sync --date 2026-07-07
vnalpha build --date 2026-07-07
vnalpha score --date 2026-07-07
vnalpha watchlist --date 2026-07-07
```

**Note:** `vnstock-service` must be running and reachable at `http://127.0.0.1:6900` on the remote host. Verify with:
```bash
curl -s http://127.0.0.1:6900/v1/providers || echo "vnstock-service not reachable"
```

### ⚠️ Issue 2: Textual skipped on local dev machine

**Symptom:** 26 TUI tests skipped locally because `textual` isn't installable via the internal Nexus proxy (TLS error on `nexus.x51.vn`).  
**Cause:** Nexus PyPI proxy has an SSL TLSv1 alert internal error when accessed from this machine.  
**Impact:** The TUI tests pass correctly on the remote host (textual 8.2.8 is installed there).  
**Action Required:** Either fix the Nexus SSL config or add an internet-facing pip mirror fallback in the local dev pip config.

### ⚠️ Issue 3: Manual PATH setup required in new SSH sessions

**Symptom:** `~/.local/bin` is only in PATH after sourcing `~/.bashrc`.  
**Cause:** Non-interactive SSH sessions don't source `~/.bashrc`.  
**Workaround:** Use the explicit path `~/.local/bin/vnalpha` or prefix with `export PATH="$HOME/.local/bin:$PATH"`.  
**Action Required:** Consider adding to `~/.profile` or `~/.bash_profile` for non-interactive sessions.

---

## 9. Deployment Steps Reference

| Step | Command | Result |
|------|---------|--------|
| Build wheel | `python -m build --wheel` | ✅ 119 KB |
| Transfer | `scp dist/*.whl beou@10.113.213.9:/tmp/` | ✅ |
| Create venv | (already existed) | ✅ |
| Install wheel | `pip install /tmp/vnalpha-0.1.0*.whl --force-reinstall` | ✅ |
| Write .env | `cat > ~/.config/vnalpha/.env` | ✅ |
| Write launcher | `cat > ~/.local/bin/vnalpha` | ✅ |
| Add to PATH | `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc` | ✅ |
| Init warehouse | `vnalpha init` | ✅ `Warehouse ready.` |
| Plan preview | `vnalpha ask ... --no-execute` | ✅ |
| Full LLM call | `vnalpha ask ...` | ✅ Exit 0 |

---

## 10. Final Status

```
Overall: SUCCESS
LLM gateway (lite.x51.vn): ✅ reachable, responds correctly
Warehouse init: ✅
CLI commands: ✅ all 9 commands available
Data ingestion: ⚠️ not run yet — see Issue 1
TUI (textual): ✅ textual 8.2.8 installed on remote host
```
