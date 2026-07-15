# FiinQuantX commercial-use decision record

> **Status:** template only — no permission is asserted by this file.
>
> GitHub must contain only the non-secret decision metadata below. Store the
> agreement, legal advice, account details and commercial correspondence in the
> organization's approved document system.

## Decision metadata

| Field | Required value |
|---|---|
| Decision reference | `UNRESOLVED` |
| Agreement/vendor reference | `UNRESOLVED` |
| Decision owner | `UNRESOLVED` |
| Legal/compliance reviewer | `UNRESOLVED` |
| Procurement/vendor reviewer | `UNRESOLVED` |
| Approved account/package | `UNRESOLVED` |
| Effective date | `UNRESOLVED` |
| Review/expiry date | `UNRESOLVED` |
| Approved SDK version | `UNRESOLVED` |
| Approved Python/OS runtime | `UNRESOLVED` |

Do not set runtime approval variables while the decision reference is
`UNRESOLVED`, `PENDING`, `TBD`, a placeholder or a free-form sentence.

## Usage-scope matrix

Allowed decisions are `ALLOW`, `DENY`, or `UNRESOLVED`. The fail-closed default
is `UNRESOLVED`.

| Scope | Decision | Constraints/evidence |
|---|---|---|
| Local SDK execution | `UNRESOLVED` | Exact account, SDK version and machine/runtime scope required |
| Single-process in-memory cache | `UNRESOLVED` | TTL, row limits and process boundary required |
| SQLite cache | `UNRESOLVED` | Retention, encryption and deletion policy required |
| Normalized local files | `UNRESOLVED` | Format, retention and redistribution restrictions required |
| DuckDB persistence | `UNRESOLVED` | User count, retention and derived-data rights required |
| Postgres/server persistence | `UNRESOLVED` | Multi-user and central-service rights required |
| Raw payload archive | `DENY` | Remains denied unless an explicit amendment allows it |
| Localhost REST response | `UNRESOLVED` | Named operator and response-size limits required |
| Internal multi-user REST exposure | `DENY` | Requires an explicit reviewed permission change |
| Public/external service exposure | `DENY` | Out of current deployment scope |
| Bulk export/download | `DENY` | Requires an explicit reviewed permission change |
| Synthetic fixtures without licensed values | `UNRESOLVED` | Manual review and provenance record required |
| Derived deterministic analytics | `UNRESOLVED` | Clarify whether derived outputs may be stored/shared |
| Feature generation | `UNRESOLVED` | Clarify persistence and downstream use |
| Model training/fine-tuning | `DENY` | Requires a separate written decision |
| Evaluation against bounded licensed rows | `UNRESOLVED` | No row output, retention or repository storage |

## Runtime activation record

After review, record only a non-secret internal decision identifier in runtime
configuration:

```text
VNSTOCK_FIINQUANTX_LICENSED=true
VNSTOCK_FIINQUANTX_LICENSE_APPROVAL_REF=<decision-id>
```

The provider remains disabled unless both values are valid. Diagnostics expose
only whether a reference is configured and a short SHA-256 fingerprint; they do
not expose the decision identifier itself.

## Persistence activation record

Warehouse-bound persistence requires a separately reviewed scope:

```text
VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true
VNALPHA_FIINQUANTX_PERSISTENCE_APPROVAL_REF=<decision-id>
```

This reference must point to a decision that explicitly permits the actual
storage target and use. A runtime-use approval does not automatically permit
DuckDB, Postgres, files, bulk export, derived analytics or model training.

## Evidence checklist

- [ ] Decision metadata is complete and points to an approved external record.
- [ ] Every intended usage scope is `ALLOW` or `DENY`; none remains ambiguous.
- [ ] SDK version, wheel integrity decision, Python version and OS are recorded.
- [ ] Account/package entitlement and quota evidence is recorded safely.
- [ ] Session, expiry, concurrency and cleanup behavior is verified.
- [ ] Timestamp, timezone, empty-response and adjustment semantics are verified.
- [ ] No credentials, session state or licensed production rows are stored here.
- [ ] Issue #105 and the OpenSpec validation ledger link the approved reference.

## Revocation

When a decision expires, is revoked or its scope changes:

1. set both acknowledgement booleans to `false`;
2. remove the approval references from runtime configuration;
3. stop the optional provider image/service;
4. apply the approved retention/deletion policy to persisted data;
5. record the revocation in issue #105 and the external decision system.
