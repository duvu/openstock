## Why

OpenStock currently has raw and canonical OHLCV but no provider-independent
corporate-action evidence. Mechanical dividends, splits, rights issues and
listing changes therefore cannot be reconciled or used safely by the later
adjustment engine.

Issue #112 introduces the evidence and ingestion boundary only. It does not
calculate adjustment factors or change downstream price basis.

## What Changes

- add `reference.corporate_actions` to the vnstock contract registry and service;
- normalize bounded KBS and VCI company-event feeds into a common taxonomy while
  preserving the complete provider payload and content hash;
- persist raw evidence before validation;
- add canonical revision, source-link, quarantine and affected-range tables;
- make repeated sync idempotent and preserve revised or conflicting evidence;
- add bounded sync/status commands to vnalpha;
- update tests, required CI and current data-contract documentation together.

## Capabilities

### Added Capabilities

- `corporate-action-ingestion`: provider-independent action evidence,
  reconciliation, revisions, conflicts, quarantine and affected-range signals.

## Impact

#113 may consume accepted canonical actions and affected ranges after this
change. No adjusted-price output is produced by this issue.
