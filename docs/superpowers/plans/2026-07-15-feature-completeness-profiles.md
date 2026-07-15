# Feature Completeness Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist versioned feature completeness and fail closed when a consumer requests evidence a snapshot cannot support.

**Architecture:** A pure evaluator maps observed feature values and history to a frozen profile result.  The feature builder persists that result with additive warehouse columns; each research consumer selects the required profile and relative-strength requirement through one shared predicate.

**Tech Stack:** Python, DuckDB, existing pandas-based feature pipeline, pytest, Typer.

---

### Task 1: Define and prove completeness policy

**Files:**
- Create: `vnalpha/src/vnalpha/features/completeness.py`
- Create: `vnalpha/tests/test_feature_completeness.py`

- [ ] **Step 1: Write the failing evaluator tests.**

```python
def test_standard_profile_rejects_a_twenty_bar_snapshot() -> None:
    result = evaluate_feature_completeness(_snapshot(bar_count=20))
    assert result.neutral_status is CompletenessStatus.INCOMPLETE
    assert "ma100" in result.missing_neutral_fields

def test_missing_benchmark_does_not_invalidate_neutral_evidence() -> None:
    result = evaluate_feature_completeness(_snapshot(bar_count=120, rs20=None))
    assert result.neutral_status is CompletenessStatus.COMPLETE
    assert result.relative_strength_status is CompletenessStatus.INCOMPLETE
```

- [ ] **Step 2: Run the tests to verify red.**

Run: `cd vnalpha && uv run pytest tests/test_feature_completeness.py -q`

Expected: FAIL because the evaluator module does not exist.

- [ ] **Step 3: Implement frozen profile and result models.**

```python
@dataclass(frozen=True, slots=True)
class FeatureCompleteness:
    profile: FeatureCompletenessProfile
    neutral_status: CompletenessStatus
    relative_strength_status: CompletenessStatus
    required_bar_count: int
    observed_bar_count: int
    missing_neutral_fields: tuple[str, ...]
    missing_relative_strength_fields: tuple[str, ...]
    rule_version: str
```

Implement one registry with 20, 120, and 252-bar rules, then evaluate every
profile deterministically without inspecting warning prose.

- [ ] **Step 4: Run the policy tests to verify green.**

Run: `cd vnalpha && uv run pytest tests/test_feature_completeness.py -q`

Expected: PASS.

### Task 2: Persist evaluated evidence and migrate legacy rows

**Files:**
- Modify: `vnalpha/src/vnalpha/warehouse/schema.py`
- Modify: `vnalpha/src/vnalpha/warehouse/migrations.py`
- Modify: `vnalpha/src/vnalpha/features/snapshot_store.py`
- Modify: `vnalpha/src/vnalpha/features/build_features.py`
- Test: `vnalpha/tests/test_features.py`
- Test: `vnalpha/tests/test_r0_gaps.py`

- [ ] **Step 1: Write failing persistence and migration tests.**

```python
def test_build_persists_profile_evidence(conn) -> None:
    build_features(conn, TARGET_DATE, universe=["FPT"])
    assert _snapshot_column(conn, "FPT", "feature_profile") == "STANDARD_120"

def test_migration_marks_existing_snapshot_legacy_unknown(conn) -> None:
    _insert_pre_profile_snapshot(conn)
    run_migrations(conn)
    assert _snapshot_column(conn, "FPT", "neutral_completeness") == "LEGACY_UNKNOWN"
```

- [ ] **Step 2: Verify red.**

Run: `cd vnalpha && uv run pytest tests/test_features.py tests/test_r0_gaps.py -q`

Expected: FAIL because the columns and persistence projection do not exist.

- [ ] **Step 3: Add additive evidence columns and build projection.**

Add idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration entries and
make `save_feature_snapshot()` persist evaluated profile evidence.  Existing
rows become `LEGACY_UNKNOWN`; a rebuilt row supplies its rule version,
observed/required history, and JSON-safe missing-field tuples.

- [ ] **Step 4: Verify green.**

Run: `cd vnalpha && uv run pytest tests/test_feature_completeness.py tests/test_features.py tests/test_r0_gaps.py -q`

Expected: PASS.

### Task 3: Enforce declared consumer requirements

**Files:**
- Modify: `vnalpha/src/vnalpha/scoring/generate_watchlist.py`
- Modify: `vnalpha/src/vnalpha/research_intelligence/breadth.py`
- Modify: `vnalpha/src/vnalpha/research_intelligence/sector_context.py`
- Modify: applicable feature-readiness module under `vnalpha/src/vnalpha/data_availability/`
- Test: `vnalpha/tests/test_scoring.py`
- Test: `vnalpha/tests/test_sector_strength_regressions.py`
- Test: applicable readiness tests

- [ ] **Step 1: Write failing boundary tests.**

```python
def test_score_skips_legacy_or_incomplete_standard_snapshot(conn) -> None:
    _insert_snapshot(conn, profile="LEGACY_UNKNOWN")
    assert score_universe(conn, TARGET_DATE, universe=["FPT"]) == 0

def test_breadth_accepts_neutral_minimum_without_relative_strength(conn) -> None:
    _insert_minimal_neutral_snapshot(conn)
    assert load_breadth_context(conn, TARGET_DATE, "VNINDEX").eligible_count == 1
```

- [ ] **Step 2: Verify red.**

Run: `cd vnalpha && uv run pytest tests/test_scoring.py tests/test_sector_strength_regressions.py -q`

Expected: FAIL because consumers only inspect row existence, freshness, and
null fields.

- [ ] **Step 3: Replace local predicates with declared profile requirements.**

Require non-legacy exact-date evidence.  Scoring and sector strength require
their standard relative-strength profile; breadth requires only its neutral
minimum.  The readiness boundary reports typed missing evidence through its
existing public-safe result contract.

- [ ] **Step 4: Verify green.**

Run: `cd vnalpha && uv run pytest tests/test_scoring.py tests/test_sector_strength_regressions.py tests/test_market_regime_builder.py -q`

Expected: PASS.

### Task 4: Validate real surfaces

**Files:**
- Modify: `openspec/changes/feature-completeness-profiles/tasks.md`

- [ ] **Step 1: Run automated gates.**

Run: `cd vnalpha && uv run pytest -q`

Run: `make lint-vnalpha && make verify-r0`

Run: `openspec validate feature-completeness-profiles --strict`

- [ ] **Step 2: Exercise command surfaces.**

Run: `cd vnalpha && uv run vnalpha build features --help`

Run: `cd vnalpha && uv run vnalpha score --help`

Run the offline feature-build then score flow against the existing fixture and
confirm an incomplete row is excluded rather than scored.

- [ ] **Step 3: Record only observed evidence.**

Check the matching OpenSpec tasks after their focused, full, and surface checks
have passed.  Keep any unavailable packaging or TUI/assistant evidence marked
as not run with a concrete reason.
