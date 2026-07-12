# Closed-loop validation evidence

Date: 2026-07-12

## Passing evidence

- Focused closed-loop and security suite: 38 passed.
- Neighboring CLI, observability, and operational-bridge suite: 72 passed with writable temporary roots.
- `make verify-r4`: 79 passed with writable temporary roots.
- `packaging/scripts/openstock-verify --ci`: 16 OK, 1 existing systemd warning, 0 failures.
- Ruff and `compileall` pass for the closed-loop package and touched integration files.
- LSP diagnostics report zero errors for the closed-loop package, command handlers, redaction, deploy CLI, and TUI operational bridge.
- Manual CLI flow passes prepare, status, validation, verification, promotion, and rollback. Rejected proposal, missing sandbox runner, and `--force` paths return non-zero; `--force` is absent from promote help.

## Repository-wide residuals

- `make lint-vnalpha` remains blocked by pre-existing edits under `vnalpha/src/vnalpha/research_automation/` and `vnalpha/src/vnalpha/warehouse/migrations.py` (import ordering, unused imports, and an undefined `Mapping`).
- Isolated `make test-vnalpha` reaches eight pre-existing failures in the same research-automation migration/schema work and its safety scan (`research_automation.models` dataclass construction, six extra migration tables, and the existing `investment advice` source literal).
- The default-home variants additionally fail in this managed environment because `/home/beou/.local` is read-only; the isolated runs use temporary log, warehouse, and workspace roots.
- No PR is available in this workspace, so task 10.10 remains open.
