# Design: FiinQuantX full data expansion

## Capability lifecycle

Every candidate dataset advances only with evidence:

```text
DOCUMENTED
→ RUNTIME_VERIFIED
→ CONTRACT_DEFINED
→ IMPLEMENTED
→ SERVICE_EXPOSED
→ PERSISTED
→ CONSUMER_VERIFIED
→ E2E_VERIFIED
```

`supported=true` is reserved for a service request that can execute under the
current exact SDK, credentials and entitlement. A documented
method, registered contract or REST route alone is insufficient.

## Access policy

FiinQuantX has no runtime or warehouse-persistence approval gate. Access is
controlled only by the exact supported SDK and local credentials. No approval
boolean, reference, fingerprint or expiry state is accepted or reported.

## Dataset policy

Each enabled vertical must declare its canonical name/version, consumer,
bounded request modes, keys, timing, units, signs, price basis, currency,
revisions, current-versus-historical eligibility, typed failures and safe
lineage. Unknown SDK shapes, units, entitlement and timing remain disabled or
explicitly deferred.

## Realtime policy

Realtime and streaming methods use a separate bounded subscription lifecycle
with cancellation, backpressure, shutdown and ephemeral default retention.
They cannot be routed through synchronous fetch or a normal REST GET request.
