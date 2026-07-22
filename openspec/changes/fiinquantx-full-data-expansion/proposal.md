# Change: FiinQuantX full data expansion

## Status

Proposed. This program is the normative specification for GitHub epic #356 and
its delivery issues #357–#367.

## Why

FiinQuantX is an optional licensed provider. Existing synchronous support is
limited to daily equity/index OHLCV and current membership observations; the
remaining documented surface is not runtime truth or a contract to expose data.

## What Changes

- Remove runtime and persistence approval gates.
- Publish one checked-in capability inventory and bounded opt-in probe harness.
- Certify the four existing synchronous datasets before using them as a pattern.
- Add only licensed-runtime-verified, consumer-backed reference, market,
  flow, valuation and fundamental verticals.
- Keep realtime methods in an explicit data-only subscription lifecycle, never
  in synchronous `PluginRuntime.fetch()`.
- Produce an exact-SHA clean-host acceptance matrix that leaves unsupported
  and deferred capabilities disabled.

## Boundaries

- `vnalpha` only uses provider-independent vnstock contracts and service APIs.
- No broker, account, order, margin, transfer, position or execution surface.
- No raw licensed payload archive, public redistribution or model training.
- Current observations are never presented as historical facts.

## Delivery Order

1. #357 removal of approval gates and #358 inventory/probes.
2. #359 foundation certification and #360–#365 verified synchronous verticals.
3. #366 separately specified realtime lifecycle when its evidence supports it.
4. #367 clean-host acceptance and final capability matrix.
