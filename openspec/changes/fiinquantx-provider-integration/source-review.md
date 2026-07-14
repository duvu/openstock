# Source review: FiinQuantX

## Reviewed source

Official repository:

```text
https://github.com/fiinquant/fiinquantx
```

Reviewed branch/commit:

```text
main
abb1e038f3e7401ab770067c5d7a539a06823097
```

## Verified observations

1. The public repository is a binary distribution repository rather than an open-source SDK repository.
2. `README.md` contains only the project name and does not document imports, authentication, method signatures, schemas, quotas, or licensing behavior.
3. The repository exposes a PEP-503-style package index under:

   ```text
   docs/simple/fiinquantx/index.html
   ```

4. The package index links Python wheels published through GitHub Releases.
5. The newest wheel listed at the reviewed commit is:

   ```text
   fiinquantx-0.1.64-py3-none-any.whl
   ```

6. Recent commits primarily update distributed wheel versions. The repository does not expose implementation source, type stubs, generated API documentation, schemas, or test fixtures.

## Consequence for implementation

The OpenStock implementation must not infer the SDK contract from product marketing or from undocumented assumptions.

Before a production adapter is written, an authorized developer must use a licensed FiinQuantX installation and official documentation to capture:

- official installation command and supported Python versions;
- package/import names;
- authentication/session lifecycle;
- public classes, functions, parameters, return types, and exceptions;
- dataset entitlements and quota metadata;
- raw field names, units, timestamps, time zones, pagination, and revision behavior;
- publication-time fields for historical fundamentals;
- license permissions for local persistence, derived data, testing, and service exposure.

## Repository and licensing constraints

- Do not commit or redistribute the FiinQuantX wheel.
- Do not copy proprietary SDK source or documentation into OpenStock.
- Do not commit credentials, tokens, cookies, account IDs, or customer-specific entitlement data.
- Do not commit raw licensed production payloads unless the commercial agreement explicitly permits redistribution.
- Offline tests must use synthetic fixtures that reproduce the discovered shapes without containing licensed records.
- Live tests must be opt-in and require a licensed local environment.

## Initial integration assumption

FiinQuantX will be integrated as an optional authenticated provider behind the existing `ProviderPlugin`, `PluginRegistry`, `PluginRouter`, `PluginRuntime`, `DataResult`, auth, diagnostics, and contract-validation layers.

No direct FiinQuantX call may bypass `PluginRuntime` in the service path.

## Discovery output required before runtime work

The discovery slice must produce a local, reviewable contract inventory without exposing secrets or proprietary raw data:

```text
provider version tested
supported Python versions
installation mechanism
import surface
public method inventory
auth and entitlement behavior
verified dataset matrix
parameter matrix
normalized field mapping
exception taxonomy
rate/quota behavior
license decision record
synthetic fixture plan
```

Any capability not verified through the licensed SDK and official documentation remains `unsupported` or `discovery_pending` and must not be advertised by the provider.