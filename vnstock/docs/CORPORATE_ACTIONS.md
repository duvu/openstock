# Corporate-action data contract

> **Status:** current implementation for issue #112.

`reference.corporate_actions` exposes bounded provider-normalized evidence for
corporate events. It does not calculate adjusted prices.

## Providers

KBS and VCI currently declare this dataset as `partial`. Their event feeds are
market-data evidence and are not described as official issuer disclosures.
Unsupported providers fail explicitly; a supported provider returning no rows is
a valid empty result.

## Required columns

```text
provider_event_id
symbol
action_type
provider
source_reference
source_version
content_hash
source_payload_json
```

Optional fields include announcement, ex, record and effective dates; cash,
ratio, subscription and reference-price terms; currency and title. `ratio` is
normalized as new/resulting shares per existing share: `1:2` split becomes `2.0`,
`2:1` consolidation becomes `0.5`, and a `2:1` rights entitlement becomes `0.5`
new share per existing share. `ratio_text` preserves the provider wording.

Supported canonical action types are:

```text
CASH_DIVIDEND
STOCK_DIVIDEND
STOCK_BONUS
SPLIT
CONSOLIDATION
RIGHTS_ISSUE
REFERENCE_PRICE_ADJUSTMENT
ADDITIONAL_LISTING
SYMBOL_CHANGE
DELISTING
```

Unclassified events remain `OTHER` at the provider boundary and are quarantined
by vnalpha rather than silently promoted.

## Service request

```bash
curl 'http://127.0.0.1:6900/v1/reference/corporate-actions?symbol=SSI&start=2024-01-01&end=2024-12-31&source=VCI'
```

The response uses the standard vnstock-service envelope. Source payloads are
preserved for audit but remain untrusted evidence.
