# Deduplicated lane evidence

Commit: `02eff49940b5fd79d4e8acd873ae91f9f006b260`

The environment is the same local worktree, operating system, CPU, memory,
Python, DuckDB, pytest and dependency set recorded in `baseline.md`.

## Canonical full plan

```bash
cd vnalpha && uv run python ../scripts/run-test-suite.py \
  --suite shared-smoke --suite migration --suite vnalpha-data \
  --suite vnalpha-research --suite vnalpha-application --plan
```

| Check | Result |
| --- | ---: |
| Manifest-resolved paths | 275 |
| Unique resolved paths | 275 |
| Collected `test_*.py` files | 275 |
| Missing collected files | 0 |
| Extra planned files | 0 |
| `make -n verify-hardening` full-runner calls | 1 |
| `make -n verify-hardening` `verify-r0` calls | 0 |
| `make -n verify-hardening` `verify-r4` calls | 0 |
| `make -n verify-hardening` `openstock-verify --ci` calls | 1 |

The standalone `make verify-r0` and `make verify-r4` commands remain defined;
the aggregate no longer runs either around the canonical full runner.

## Runtime checks

| Command | Result | Wall time | Comparison |
| --- | --- | ---: | --- |
| `make test-vnalpha-smoke` | 154 passed | 42.72 s | Meets the 60 s fast-smoke budget. |
| `make test-vnalpha` | 3,303 passed | 625.00 s | Baseline sequential full run: 634.17 s. |

The measured 9.17 s local full-run difference is recorded, but is not claimed as
a material performance result by itself: it is within ordinary workstation and
fixture variation. The proven optimization is that `verify-hardening` no longer
repeats the 11 R0/R4 files and no longer invokes `openstock-verify --ci` twice.
Future required-PR timing claims require equivalent GitHub runner evidence.
