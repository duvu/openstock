# Benchmark-Aware Relative Strength Design

## Goal

Implement GitHub issue #82 so relative-strength evidence always identifies the
benchmark actually used, while existing VNINDEX snapshots remain readable.

## Scope

The delivery adds a versioned, active-date-aware benchmark registry; normalized
20- and 60-session relative-strength evidence; deterministic benchmark policy;
benchmark-specific readiness checks; and benchmark lineage in scored/deep
analysis output. It supports VNINDEX, VN30, HNXINDEX, and UPCOMINDEX. It does
not add sector indexes, trading behavior, or a new research-artifact store.

## Alternatives considered

1. **Keep benchmark-specific feature columns.** This preserves current queries
   but cannot safely represent a second benchmark without more mislabeled
   fields.
2. **Add one `benchmark_symbol` to `feature_snapshot`.** This is smaller but a
   rebuild for another benchmark overwrites the prior reference for the same
   symbol and date.
3. **Normalized relative-strength snapshots (chosen).** One evidence row per
   symbol, date, benchmark, and horizon retains exact semantics, supports
   multiple references, and lets existing VNINDEX columns remain a transitional
   compatibility projection.

## Architecture

### Registry and deterministic selection

`benchmark_definition` stores benchmark symbol, benchmark type, exchange and
universe applicability, role, source, methodology version, and inclusive
active dates. Migration seeds the four supported Vietnam indexes with an
OpenStock-controlled `v1` methodology.

`BenchmarkPolicy` resolves a benchmark from an explicit requested symbol when
it is active and applicable; otherwise it uses the symbol taxonomy as of the
target date: HOSE selects VNINDEX, HNX selects HNXINDEX, and UPCOM selects
UPCOMINDEX. VN30 is a registered secondary benchmark and becomes the selected
reference only when explicitly requested. An absent, inactive, or inapplicable
benchmark fails closed with a typed remediation rather than falling back to a
differently labeled index.

### Relative-strength evidence

`relative_strength_snapshot` has the identity
`(symbol, date, benchmark_symbol, horizon_sessions)`. Each row stores the
relative return, actual source and benchmark bar dates, row counts, status,
generation version, and a JSON lineage object containing both canonical bar
provenances. The build service writes 20- and 60-session rows only after the
selected benchmark's canonical coverage can be aligned to the symbol bars.
Missing, stale, or insufficient benchmark coverage is stored as explicit
non-success evidence and cannot be scored as successful relative strength.

The existing `rs_20d_vs_vnindex` and `rs_60d_vs_vnindex` feature columns stay
readable. A schema migration backfills normalized rows from them using
`benchmark_symbol = VNINDEX` and their existing metadata/lineage. New builds
only project values to those legacy columns for VNINDEX. A build against VN30,
HNXINDEX, or UPCOMINDEX never writes a value labeled `vs_vnindex`.

### Consumer and universe changes

Scoring loads relative-strength values through the normalized evidence table
and carries the selected benchmark plus bar dates into candidate lineage. Deep
analysis and `/lineage` expose that real benchmark lineage instead of inferring
VNINDEX from a field name. Legacy callers that read old VNINDEX feature columns
continue to receive the same semantic values during migration.

The default feature universe draws only active common equities and excludes all
registered benchmarks, even if a classification row is absent. Explicitly
supplied index symbols are rejected from common-equity feature/sector work.

### Readiness and error behavior

Readiness validates a successful normalized row for the requested/default
benchmark and its required horizons, including the source and benchmark bar
dates. Failures report the actual benchmark and a bounded index-download/build
remediation command. Feature, score, and deep-analysis results preserve their
existing `SUCCESS`, `PARTIAL`, and `FAILED` meaning and use the existing
correlation and audit path.

## Data flow

```text
symbol taxonomy + requested benchmark
            -> BenchmarkPolicy -> benchmark_definition
canonical symbol bars + canonical benchmark bars
            -> relative_strength_snapshot (20d, 60d, lineage)
            -> scoring / readiness / deep-analysis lineage
```

## Validation matrix

- a VN30 calculation stores `benchmark_symbol = VN30` and never writes a
  VNINDEX-labeled value;
- HOSE, HNX, and UPCOM symbols resolve the documented exchange benchmark;
- an inactive or unavailable benchmark produces typed incomplete evidence and
  actionable remediation;
- every registered index and every explicit non-common-equity symbol is
  excluded/rejected from common-equity feature and sector universes;
- VNINDEX legacy rows backfill with unchanged values and remain readable;
- score, readiness, deep-analysis, CLI, TUI command routing, and `/lineage`
  show the actual benchmark and source dates;
- multiple benchmarks for one symbol/date coexist without overwriting;
- full repository, package, and affected compatibility paths are validated.
