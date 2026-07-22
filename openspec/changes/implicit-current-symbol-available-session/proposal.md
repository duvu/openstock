## Why

An implicit current-symbol request can resolve to today's configured market
session even when the target and benchmark have no canonical bar for it. The
readiness path must select the most recent aligned usable evidence before it
provisions features or scores.

## What Changes

- Preserve an implicit current-symbol request as `today` until readiness owns
  evidence-date selection.
- Select the latest aligned target and VNINDEX canonical session with the
  required lookback when the current session is not yet available.
- Keep explicit dates strict and make all readiness remediation use the chosen
  effective session.
