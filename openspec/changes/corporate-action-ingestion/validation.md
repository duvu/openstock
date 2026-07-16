# Validation: Corporate-action ingestion

## Status

```text
Provider contract and normalization: implemented
Warehouse raw/canonical/revision contracts: implemented
Bounded sync and status commands: implemented
Focused offline tests: pass
Full repository CI and exact final SHA: pending pull request
```

## Required final commands

```bash
python scripts/check-repo-consistency.py
cd vnstock && ruff check . && ruff format --check .
cd vnstock && pytest -q tests/contracts/test_corporate_action_contract.py tests/contracts/test_builtin_provider_capabilities.py
cd vnalpha && pytest -q tests/test_corporate_action_ingestion.py tests/test_vnstock_corporate_action_client.py
make verify-r0
make test-vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnalpha-dist ./vnalpha
python -m build --wheel --sdist --no-isolation --outdir /tmp/vnstock-dist ./vnstock
```

## Evidence

| UTC timestamp | Commit SHA | Phase/task | Command | Exit | Result summary | Evidence artifact |
|---|---|---|---|---:|---|---|
| 2026-07-16T00:10:00Z | `local source export + working tree` | 1.1–2.4 | focused vnstock corporate-action and provider-capability contracts | 0 | 135 tests passed | local command transcript |
| 2026-07-16T00:10:00Z | `local source export + working tree` | 2.1–2.4 | focused vnalpha client, ingestion, revision, conflict and provisioning tests | 0 | 16 tests passed | local command transcript |
| 2026-07-16T00:20:00Z | `local source export + working tree` | 1.1–1.4 | required vnstock provider/canonical contract selection | 0 | 508 tests passed | local command transcript |
| 2026-07-16T00:35:00Z | `local source export + working tree` | 2.1–3.2 | R0 constituent suite | 0 | 70 tests reached 100% | local command transcript |
| 2026-07-16T00:40:00Z | `local source export + working tree` | 1.1–3.2 | Ruff, repository consistency and both wheel/sdist builds | 0 | all checks and builds passed | local command transcript |

Final implementation SHA: `pending pull request`
