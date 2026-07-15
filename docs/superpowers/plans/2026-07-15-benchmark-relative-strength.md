# Benchmark-Aware Relative Strength Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every persisted relative-strength value, score, and readiness result identify and validate its real benchmark.

**Architecture:** Add a registry and deterministic resolver, then persist one normalized evidence row per symbol/date/benchmark/horizon. Keep the old VNINDEX fields as a compatibility projection only, while scoring and readiness consume the normalized rows.

**Tech Stack:** Python 3.13, DuckDB, pandas, Typer, pytest.

---

### Task 1: Add benchmark registry and normalized storage

**Files:**
- Create: `vnalpha/src/vnalpha/features/benchmarks.py`
- Modify: `vnalpha/src/vnalpha/warehouse/schema.py`
- Modify: `vnalpha/src/vnalpha/warehouse/migrations.py`
- Test: `vnalpha/tests/test_benchmark_registry.py`

- [ ] **Step 1: Write failing policy and migration tests.**

```python
def test_resolve_benchmark_selects_exchange_default(conn):
    assert resolve_benchmark(conn, "FPT", date(2026, 7, 10)).symbol == "VNINDEX"
    assert resolve_benchmark(conn, "HNX", date(2026, 7, 10)).symbol == "HNXINDEX"

def test_migration_backfills_vnindex_legacy_rows(conn):
    run_migrations(conn)
    assert _relative_strength_row(conn, "FPT", "2026-07-10", "VNINDEX", 20)
```

- [ ] **Step 2: Run the new test.**

Run: `cd vnalpha && uv run pytest tests/test_benchmark_registry.py -q`

Expected: FAIL because the resolver and normalized table do not exist.

- [ ] **Step 3: Implement the registry and resolver.**

```python
@dataclass(frozen=True, slots=True)
class BenchmarkDefinition:
    symbol: str
    exchange: str | None
    role: BenchmarkRole
    active_from: date | None
    active_to: date | None

def resolve_benchmark(
    conn: duckdb.DuckDBPyConnection,
    symbol: str,
    as_of: date,
    requested_symbol: str | None = None,
) -> BenchmarkDefinition: ...
```

Seed VNINDEX, VN30, HNXINDEX, and UPCOMINDEX. Choose an exchange default from
as-of taxonomy and reject unavailable/inapplicable explicit choices. Create
`benchmark_definition` and `relative_strength_snapshot`, keyed by
`(symbol, date, benchmark_symbol, horizon_sessions)`. Backfill non-null legacy
values as VNINDEX with existing metadata and lineage using `ON CONFLICT DO NOTHING`.

- [ ] **Step 4: Run tests and commit.**

Run: `cd vnalpha && uv run pytest tests/test_benchmark_registry.py tests/test_symbol_lifecycle.py -q`

Expected: PASS.

Commit: `git commit -m "feat(vnalpha): add benchmark registry"`.

### Task 2: Build explicit relative-strength evidence

**Files:**
- Modify: `vnalpha/src/vnalpha/features/relative_strength.py`
- Modify: `vnalpha/src/vnalpha/features/build_features.py`
- Test: `vnalpha/tests/test_features.py`
- Test: `vnalpha/tests/test_benchmark_relative_strength.py`

- [ ] **Step 1: Write failing multi-benchmark tests.**

```python
def test_vn30_reference_is_not_written_as_vnindex(conn):
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")
    assert _snapshot_benchmark(conn, "FPT", TARGET_DATE) == "VN30"
    assert _legacy_vnindex_value(conn, "FPT", TARGET_DATE) is None

def test_two_benchmarks_for_one_symbol_date_coexist(conn):
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VNINDEX")
    build_features(conn, TARGET_DATE, universe=["FPT"], benchmark_symbol="VN30")
    assert _reference_count(conn, "FPT", TARGET_DATE) == 4
```

- [ ] **Step 2: Run the new test.**

Run: `cd vnalpha && uv run pytest tests/test_benchmark_relative_strength.py -q`

Expected: FAIL because feature builds persist no normalized rows.

- [ ] **Step 3: Persist aligned source and benchmark evidence.**

Calculate 20- and 60-session rows under the actual resolved benchmark, including
actual source/benchmark bar dates, row counts, status, and canonical lineage.
Project a value into `rs_*_vs_vnindex` only for VNINDEX and set those
compatibility fields null for other benchmarks. Default features use active
common equities and exclude every registered benchmark; explicit non-equities
are rejected.

- [ ] **Step 4: Run tests and commit.**

Run: `cd vnalpha && uv run pytest tests/test_features.py tests/test_benchmark_relative_strength.py tests/test_symbol_lifecycle.py -q`

Expected: PASS.

Commit: `git commit -m "feat(vnalpha): persist benchmark-aware relative strength"`.

### Task 3: Use actual benchmark evidence at consumer boundaries

**Files:**
- Modify: `vnalpha/src/vnalpha/scoring/generate_watchlist.py`
- Modify: `vnalpha/src/vnalpha/data_availability/checks.py`
- Modify: `vnalpha/src/vnalpha/cli_app/build.py`
- Modify: `vnalpha/src/vnalpha/cli_app/data.py`
- Modify: `vnalpha/src/vnalpha/tools/research_intelligence.py`
- Test: `vnalpha/tests/test_scoring.py`
- Test: `vnalpha/tests/test_deep_analysis_readiness.py`
- Test: `vnalpha/tests/test_data_provisioning.py`

- [ ] **Step 1: Write failing score/readiness/CLI tests.**

```python
def test_score_lineage_contains_actual_benchmark(conn):
    score_universe(conn, TARGET_DATE, universe=["FPT"])
    assert _candidate_lineage(conn, "FPT", TARGET_DATE)["benchmark_symbol"] == "VN30"

def test_readiness_rejects_missing_selected_benchmark_evidence(conn):
    result = ensure_deep_analysis_ready(conn, "FPT", TARGET_DATE)
    assert result.is_ready is False
    assert "VN30" in result.failure_summary()
```

- [ ] **Step 2: Run the new tests.**

Run: `cd vnalpha && uv run pytest tests/test_scoring.py tests/test_deep_analysis_readiness.py tests/test_data_provisioning.py -q`

Expected: FAIL in the new benchmark-lineage assertions.

- [ ] **Step 3: Route consumers through normalized evidence.**

Score from one successful 20/60 pair for the selected benchmark and copy its
symbol, dates, and canonical provenance into candidate lineage. Require the
same rows for readiness and expose them through feature/deep-analysis lineage.
Add `--benchmark` to both feature-build CLI surfaces. Missing/stale evidence
returns incomplete readiness with bounded index-download plus feature-build
remediation, never a differently labeled fallback.

- [ ] **Step 4: Run behavior tests and commit.**

Run: `cd vnalpha && uv run pytest tests/test_scoring.py tests/test_deep_analysis_readiness.py tests/test_data_provisioning.py tests/test_cli_contract.py tests/test_command_handlers.py tests/test_tui.py -q`

Expected: PASS except separately documented baseline failures.

Commit: `git commit -m "feat(vnalpha): expose benchmark lineage in research outputs"`.

### Task 4: Validate and publish

**Files:**
- Modify: `vnalpha/docs/FEATURES.md`
- Modify: `docs/superpowers/plans/2026-07-15-benchmark-relative-strength.md`

- [ ] **Step 1: Document selection and compatibility.**

Describe the supported indexes, default selection, explicit `--benchmark`, and
the benchmark fields shown by lineage/readiness.

- [ ] **Step 2: Run quality gates and manual CLI checks.**

Run: `cd vnalpha && uv run ruff check src tests`

Run: `cd vnalpha && uv run pytest -q`

Run: `make verify-r0`

Run: `cd vnalpha && uv run vnalpha build features --help`

Run: `cd vnalpha && uv run vnalpha data build features --help`

Expected: required checks pass; pre-existing baseline failures are named; both
CLI help surfaces display `--benchmark`.

- [ ] **Step 3: Commit and open a draft PR.**

Commit: `git commit -m "docs(vnalpha): document benchmark-aware relative strength"`.

The PR body begins with `Closes #82` and includes exact validation evidence.
