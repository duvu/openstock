# Design: Close Phase 5 Alpha Discovery TUI Gaps

## Overview

This change is a closure-hardening pass for Phase 5. It does not add a new product phase. It makes the existing Phase 5 workflow executable, persistent, explainable, and testable end to end.

Target closure flow:

```text
CLI command
→ shared date resolver
→ warehouse connection and migrations
→ feature build
→ score candidate records
→ persist candidate_score
→ build daily_watchlist from candidate_score
→ TUI reads persisted watchlist and candidate detail
```

The key rule is: scoring output must be persisted before it is displayed. TUI should explain the persisted research record, not recompute an independent view.

## Gap review

### Gap 1. CLI commands are placeholders

`vnalpha build features`, `vnalpha score`, `vnalpha watchlist`, and `vnalpha tui` must invoke implementation modules. The CLI is the operational boundary used by `Makefile`, so Phase 5 cannot be considered closed while these commands are placeholders.

### Gap 2. `candidate_score` is not authoritative

The schema has `candidate_score`, but watchlist generation currently saves directly to `daily_watchlist`. Phase 5 requires candidate records with score breakdown, evidence, risk flags, setup type, and lineage. The candidate score table should be the single source of truth for scored candidates.

### Gap 3. TUI detail recomputes instead of reading persisted records

The detail screen should read `candidate_score` and related lineage/evidence. Feature snapshots may be displayed as supporting context, but the visible candidate score must match the persisted record.

### Gap 4. Candidate taxonomy is inconsistent

The archived spec references simple candidate classes, while scoring engine v1 uses setup/stage-oriented classes. Closure must choose one canonical taxonomy for Phase 5 and consistently apply it.

Recommended decision: keep scoring engine v1 classes as the Phase 5 canonical taxonomy and update the spec delta accordingly, while preserving older enum values only for backward compatibility.

### Gap 5. Date handling is inconsistent

`today` should resolve once through a shared helper. CLI, scoring, watchlist, and TUI should all use the same date resolver.

### Gap 6. Tests are not end-to-end enough

Current tests validate help text and module-level scoring. Closure requires CLI tests and warehouse-backed integration tests.

## Implementation design

### 1. Shared date resolver

Add:

```text
vnalpha/core/dates.py
```

Responsibilities:

- accept `today`;
- accept ISO `YYYY-MM-DD` dates;
- return canonical ISO date string;
- reject invalid date values with a clear CLI error;
- be used by CLI, feature build, scoring, watchlist, and TUI.

### 2. CLI command wiring

Update:

```text
vnalpha/src/vnalpha/cli.py
```

Required behavior:

```text
vnalpha build features --date <date>
→ run migrations
→ call features.build_features(...)
→ print built/skipped counts

vnalpha score --date <date>
→ run migrations
→ score feature_snapshot rows
→ persist candidate_score rows
→ print scored/persisted counts

vnalpha watchlist --date <date>
→ run migrations
→ generate daily_watchlist from candidate_score
→ print saved count or explicit no-candidate message

vnalpha tui --date <date>
→ launch VnAlphaApp(date=<resolved-date>)
```

`make features`, `make score`, and `make tui` should work without additional flags.

### 3. Candidate score persistence

Add repository helpers:

```text
save_candidate_score(conn, candidate)
get_candidate_score(conn, symbol, date)
get_candidate_scores(conn, date, min_score=None)
```

Scoring persistence should write:

- symbol;
- date;
- composite score;
- candidate class;
- setup type;
- all sub-scores;
- evidence JSON;
- risk flags JSON;
- lineage JSON.

Evidence should be deterministic and explain why the candidate was scored. It can include feature facts, rule outcomes, and score component reasons.

Lineage should include enough fields for Phase 6 outcome tracking:

- feature date;
- source feature snapshot identity;
- scoring version;
- scoring config version or hash when available;
- generated timestamp;
- source service/provider lineage when available.

### 4. Watchlist generation from candidate scores

Refactor watchlist generation:

```text
candidate_score
→ filter by date and min_score
→ sort by score descending
→ persist daily_watchlist ranks
```

Do not recompute scores inside watchlist generation. If no candidate meets criteria, return an explicit no-candidate result.

### 5. Candidate taxonomy alignment

Use scoring engine v1 classes as canonical for Phase 5:

```text
STAGE1
STAGE2
BREAKOUT
MOMENTUM
MEAN_REVERT
IGNORE
```

If `IGNORE` is not currently emitted, add it for below-threshold or unqualified cases, or document that ignored symbols are stored as rejected records.

Keep legacy enum values only for compatibility, not as Phase 5 display output.

### 6. TUI data flow

Update TUI screens:

```text
WatchlistScreen
→ read daily_watchlist
→ display rank, symbol, score, class, setup, flags

DetailScreen
→ read candidate_score for symbol/date
→ display score breakdown, evidence, risk flags, setup, lineage
→ optionally show feature_snapshot values below the persisted candidate explanation

RejectedScreen
→ read rejected_symbol rows

QualityScreen
→ read provider/data quality records where available
```

TUI should use the same resolved date that CLI passes into `VnAlphaApp`.

### 7. Research-language boundary

Add a single test fixture for disallowed execution-style wording. Tests should scan CLI and TUI user-facing strings. The output should consistently use research terms such as:

```text
candidate
watchlist
monitor
setup
evidence
risk flag
lineage
quality
```

### 8. Test strategy

Add tests:

```text
vnalpha/tests/test_dates.py
vnalpha/tests/test_cli_phase5_workflow.py
vnalpha/tests/test_candidate_score_persistence.py
vnalpha/tests/test_watchlist_from_candidate_scores.py
vnalpha/tests/test_tui_candidate_detail.py
vnalpha/tests/test_research_language_boundary.py
```

Test layers:

1. unit tests for date resolver;
2. repository tests for candidate_score save/read;
3. scoring tests proving persisted candidate rows include evidence and lineage;
4. watchlist tests proving daily_watchlist is generated from candidate_score;
5. CLI tests proving commands do not print placeholder output;
6. TUI data-loading tests using in-memory DuckDB or temporary warehouse fixture;
7. boundary tests for user-facing strings.

## Migration and compatibility

No warehouse destructive migration is required if the current schema is retained.

If additional lineage columns are needed later, prefer JSON inside `lineage_json` for Phase 5 closure instead of schema churn.

## Closure decision

After this change, Phase 5 can be marked operationally closed when CLI, persistence, TUI, and tests all agree with the Phase 5 OpenSpec requirements.
