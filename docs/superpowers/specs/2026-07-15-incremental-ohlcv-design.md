# Incremental OHLCV Sync and Repair Design

## Goal

Implement GitHub issue #79: deterministic daily OHLCV synchronization, Vietnam
trading-session gap detection, and bounded idempotent repair without allowing
invalid or incomplete data to silently enter research artifacts.

## Scope

The first delivery covers daily (`1D`) equity OHLCV only. It adds a local,
versioned Vietnam-session policy with explicit holiday input, a canonical/raw
watermark, persisted typed gap evidence, and commands for daily sync, gap
inspection, and repair. It does not add tick data, order-book data, execution,
or a provider-owned calendar contract.

## Alternatives considered

1. **Weekdays only.** Smallest implementation, but incorrectly reports public
   holidays as data gaps and does not meet the ticket's explicit holiday
   requirement.
2. **Provider-derived calendar.** Can reflect a provider's current view, but
   is not reproducible and makes gap outcomes depend on provider availability.
3. **Versioned local session policy with explicit holiday input (chosen).**
   Deterministic and testable. The initial policy treats weekdays as expected
   sessions except for supplied holiday dates; a later source-backed calendar
   can be added as another versioned policy without changing the gap contract.

## Architecture

### Session and watermark services

`TradingCalendarService` produces expected daily sessions for an inclusive
date range from a `VietnamSessionCalendar` value object. `OHLCVWatermarkService`
reads the latest canonical and raw observations for one symbol/interval and
uses the later safe coverage point with a configurable overlap-session count to
derive the next request start. All dates are normalized once as Vietnam market
dates before any database or provider call.

### Typed gap contract

`OHLCVGapKind` is an enum, not message text:

- `NOT_YET_PUBLISHED` — an expected session after the resolved market date;
- `SUSPENDED_OR_INACTIVE` — lifecycle evidence makes an observation optional;
- `PROVIDER_EMPTY` — a bounded provider request completed without rows;
- `TRUE_GAP` — a published expected session has no canonical observation;
- `HOLIDAY_OR_NON_TRADING` — excluded from missing-bar counts but retained in
  the inspection result when requested.

`OHLCVGapDetector` combines session policy, current symbol lifecycle, canonical
coverage, and recorded bounded-ingestion evidence. `OHLCVGapReport` carries
the typed status, before/after coverage, provider/run references, and ordered
remediation steps. It never branches on rendered warning text.

### Persistence and repair

`ohlcv_gap_observation` stores detection run, symbol, interval, session date,
gap kind, calendar version, canonical/raw evidence, first/last detection, and
resolution reference. Its key permits repeated detection to refresh evidence
without duplicating an unresolved observation.

`OHLCVRepairService` validates a nonempty bounded symbol/date range, detects
repairable true gaps, requests only their enclosing bounded range, rebuilds
canonical data for the selected symbol, reloads coverage, and persists the
terminal gap report. The repair is idempotent: a repeat with no true gaps does
not call the provider or rebuild canonical data. Partial, empty, and failed
provider outcomes remain explicit and cannot be presented as repaired.

### Surfaces and observability

The data provisioning service becomes the single callable boundary for daily
sync, gaps, and repair. The Typer data CLI exposes:

```text
vnalpha data sync daily [--date DATE] [--overlap-sessions N]
vnalpha data gaps [SYMBOL] [--from DATE] [--to DATE]
vnalpha data repair ohlcv SYMBOL --from DATE --to DATE
```

`/data` routes the equivalent actions through the same service. Start, provider
request, canonical rebuild, reload, and truthful terminal events use one
correlation ID. Public failures contain only allowlisted messages and valid,
bounded remediation commands.

## Backward compatibility

Existing `sync ohlcv`, `data download ohlcv`, `build canonical`, and one-symbol
ensure flows retain their signatures and defaults. Incremental behavior is
opt-in through the new daily action; legacy callers continue to pass an explicit
range or their existing provider defaults. Existing `symbol_master` rows without
lifecycle metadata preserve their prior active behavior.

## Validation matrix

- clean series with a nonzero overlap requests only the expected incremental
  range;
- weekends and configured holidays are not true gaps;
- suspended/inactive rows are separately reported and not repaired;
- published missing sessions persist as true gaps;
- empty/partial/failed provider responses preserve typed unresolved evidence;
- a corrected provider row is canonicalized, resolves the gap, and is safe to
  repeat;
- invalid request ranges fail before provider or database mutation;
- CLI, `/data`, readiness evidence, legacy sync, audit correlation, and
  packaged/repository validation gates are exercised where affected.
