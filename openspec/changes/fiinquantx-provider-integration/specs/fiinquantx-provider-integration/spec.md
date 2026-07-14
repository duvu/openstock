# fiinquantx-provider-integration Specification Delta

## ADDED Requirements

### Requirement: FiinQuantX shall be an optional provider

The system SHALL integrate FiinQuantX as an optional authenticated provider and SHALL keep base `vnstock` imports, registry construction, public APIs, tests, and package builds functional when the commercial SDK is not installed.

#### Scenario: Base package runs without FiinQuantX

- **WHEN** a user installs the normal `vnstock` package without FiinQuantX
- **THEN** importing `vnstock` succeeds
- **AND** constructing the built-in plugin registry succeeds
- **AND** existing providers remain available
- **AND** FiinQuantX diagnostics report an unavailable or not-installed state without exposing a traceback to normal callers

#### Scenario: Approved SDK is installed

- **WHEN** the approved FiinQuantX SDK version is installed
- **AND** authentication and entitlement requirements are satisfied
- **THEN** the registry exposes the implemented FiinQuantX capabilities
- **AND** diagnostics identify the tested SDK version
- **AND** no proprietary wheel or SDK source is copied into the OpenStock package

### Requirement: Licensed SDK discovery shall precede enabled capabilities

The system SHALL enable only capabilities whose SDK method, parameters, entitlement, raw schema, units, timestamps, normalization, and failure behavior have been verified using an authorized installation and official documentation.

#### Scenario: Public repository omits the API contract

- **WHEN** the public FiinQuantX repository provides a wheel but no public source, method signatures, or schemas
- **THEN** implementation records the capability as discovery pending
- **AND** does not infer a callable method or field mapping from marketing text
- **AND** does not advertise the dataset as supported

#### Scenario: Dataset contract is verified

- **WHEN** an authorized discovery run verifies an SDK method and entitlement for a dataset
- **AND** a canonical mapping and synthetic contract fixture are reviewed
- **THEN** the provider may declare that dataset implemented
- **AND** records the tested SDK version and contract evidence

### Requirement: All FiinQuantX data fetches shall use PluginRuntime

The system SHALL route every service-layer FiinQuantX data fetch through `PluginRuntime`, `PluginRouter`, and `PluginRegistry`.

#### Scenario: Canonical service endpoint requests FiinQuantX

- **WHEN** a canonical data endpoint receives `source=FIINQUANTX`
- **THEN** the request is resolved through `PluginRuntime`
- **AND** the runtime applies parameter validation, routing, auth, entitlement, health, diagnostics, and dataset-contract validation
- **AND** no direct SDK call bypasses the runtime path

#### Scenario: Runtime bypass is introduced

- **WHEN** a service or public UI attempts to call the FiinQuantX SDK directly
- **THEN** architecture regression tests fail

### Requirement: Authentication and secrets shall remain outside data requests

The system SHALL integrate the verified FiinQuantX session model through existing auth and credential abstractions. It SHALL NOT accept credentials through data methods, REST requests, MCP tools, assistant tools, TUI command arguments, DataFrame attributes, or notebooks.

#### Scenario: Provider authentication succeeds

- **WHEN** valid credentials are available through an approved credential source
- **THEN** the provider creates or reuses the verified SDK session
- **AND** reports only safe authenticated state
- **AND** data requests receive no raw credential parameters

#### Scenario: Secret reaches an error path

- **WHEN** authentication or provider execution fails
- **THEN** logs, exceptions, diagnostics, audit output, REST responses, and test output redact usernames, passwords, tokens, cookies, keys, customer identifiers, and raw auth responses

#### Scenario: REST login is requested

- **WHEN** a caller requests a FiinQuantX login/logout or raw-secret REST endpoint
- **THEN** the service does not expose that endpoint
- **AND** keeps credential management local and outside the read-only data service

### Requirement: Capability selection shall be entitlement aware

The system SHALL treat FiinQuantX support as the conjunction of implemented adapter support, compatible SDK version, available authentication, current entitlement, and accepted schema compatibility.

#### Scenario: Account lacks a dataset entitlement

- **WHEN** FiinQuantX is installed and authenticated
- **BUT** the licensed account is not entitled to the requested dataset
- **THEN** explicit `source=FIINQUANTX` returns a typed entitlement failure
- **AND** does not call the dataset method
- **AND** does not report the request as a valid empty result

#### Scenario: Auto routing evaluates FiinQuantX

- **WHEN** `source=auto` evaluates candidates
- **THEN** the router excludes FiinQuantX when installation, compatibility, auth, entitlement, health, cooldown, quota, or deployment policy makes it unusable
- **AND** records a safe routing reason

### Requirement: Explicit FiinQuantX selection shall not silently fall back

The system SHALL preserve explicit-source semantics.

#### Scenario: Explicit source fails

- **WHEN** a caller requests `source=FIINQUANTX`
- **AND** the SDK is missing, incompatible, unauthenticated, not entitled, quota exhausted, or fails to return a valid contract
- **THEN** the request returns a typed sanitized FiinQuantX failure
- **AND** does not silently return data from KBS, VCI, DNSE, TCBS, MSN, FMP, FMARKET, or another provider

#### Scenario: Auto source can fall back

- **WHEN** the caller requests `source=auto`
- **AND** configured policy permits fallback
- **THEN** the router may choose another capable provider
- **AND** the routing decision records whether FiinQuantX was rejected or a fallback was used

### Requirement: Commercial quota and connection use shall be bounded

The system SHALL enforce verified FiinQuantX rate, connection, retry, quota, and cooldown constraints.

#### Scenario: Retryable transient failure occurs

- **WHEN** the SDK returns a verified retryable timeout or temporary provider failure
- **THEN** the provider applies bounded retry with configured backoff and jitter
- **AND** respects request and connection limits
- **AND** records only safe attempt metadata

#### Scenario: Non-retryable failure occurs

- **WHEN** the request fails due to invalid input, authentication, entitlement, incompatible SDK version, or hard quota exhaustion
- **THEN** the provider does not retry
- **AND** returns the corresponding typed failure

#### Scenario: Batch request exceeds safe quota budget

- **WHEN** a batch operation would exceed the configured or observable quota budget
- **THEN** the system rejects or bounds the work before uncontrolled provider calls
- **AND** may return a structured partial result for completed items
- **AND** does not enter an unbounded retry loop

### Requirement: FiinQuantX results shall normalize to canonical dataset contracts

The system SHALL keep provider-specific names and shapes inside the FiinQuantX adapter and SHALL return canonical `DataResult` datasets to platform consumers.

#### Scenario: Market data is normalized

- **WHEN** a verified FiinQuantX market method returns data
- **THEN** the adapter normalizes symbol, date/time, timezone, interval, prices, volume/value units, adjustment state, and uniqueness keys according to the canonical contract
- **AND** contract validation runs before the result is accepted

#### Scenario: Provider schema drifts

- **WHEN** required fields disappear, types become incompatible, or units/timestamps cannot be interpreted safely
- **THEN** the result fails or degrades according to contract policy
- **AND** emits a typed schema diagnostic
- **AND** does not silently fabricate missing canonical values

#### Scenario: Result lineage is returned

- **WHEN** a FiinQuantX request succeeds
- **THEN** `DataResult` or equivalent metadata records provider, dataset, SDK version, fetched-at time, request window, safe provider method/dataset identity, quality status, validation summary, routing decision, and safe entitlement state
- **AND** contains no secret or raw auth data

### Requirement: New commercial datasets shall have explicit contracts

The system SHALL add a dataset contract before exposing any FiinQuantX dataset not already represented in the canonical registry.

#### Scenario: Index constituent history is implemented

- **WHEN** verified FiinQuantX support is added for index constituents
- **THEN** the system defines required fields, entity/index identifiers, effective dates, weights where available, uniqueness, revision semantics, freshness, and validator binding
- **AND** registers the contract before advertising the capability

#### Scenario: Market breadth or valuation is implemented

- **WHEN** verified FiinQuantX support is added for breadth or valuation history
- **THEN** the system preserves metric code, entity scope, date/period, value, unit, provider methodology/source metadata, and revision semantics
- **AND** does not merge different metric definitions under one canonical field

#### Scenario: Capability remains unverified

- **WHEN** a proposed dataset has no verified raw schema or entitlement
- **THEN** it remains unsupported or discovery pending
- **AND** no public endpoint or capability declaration claims it is available

### Requirement: Fundamentals shall preserve publication and revision semantics

The system SHALL preserve the temporal and version metadata required to use FiinQuantX financial statements without historical lookahead.

#### Scenario: Publication time is available

- **WHEN** the source provides a defensible publication or available-from timestamp
- **THEN** normalized financial records preserve that timestamp
- **AND** preserve fiscal period end, period type, consolidation scope, audit/review state, currency, unit, provider record identity, and restatement/version identity where available

#### Scenario: Publication time is unavailable

- **WHEN** a financial record has a fiscal period but no defensible publication/availability timestamp
- **THEN** the provider exposes the temporal limitation
- **AND** does not advertise the record as suitable for historical as-of analysis
- **AND** downstream consumers cannot silently substitute fiscal period end as publication time

#### Scenario: Statement is restated

- **WHEN** FiinQuantX exposes original and restated versions
- **THEN** the system preserves separate version identity or revision lineage
- **AND** does not silently overwrite the original historical record

### Requirement: Vendor-derived indicators shall remain distinguishable

The system SHALL preserve FiinQuantX-calculated indicators as vendor-derived evidence unless OpenStock independently defines and validates an equivalent canonical formula.

#### Scenario: Vendor indicator is ingested

- **WHEN** a verified vendor-derived indicator is exposed
- **THEN** the result preserves vendor indicator code/name, value, unit, date/period, SDK/provider lineage, and formula/version metadata where available
- **AND** identifies the dataset as vendor derived

#### Scenario: OpenStock score is calculated

- **WHEN** OpenStock computes its deterministic feature or score
- **THEN** a FiinQuantX vendor indicator does not silently replace that formula
- **AND** any comparison is explicit and auditable

### Requirement: Licensed data persistence and exposure shall follow an approved policy

The system SHALL define and enforce a reviewed license policy for caching, persistence, archive, export, local service response, multi-user exposure, fixtures, and derived analytics.

#### Scenario: License decision is not complete

- **WHEN** permission for raw archive, normalized persistence, export, or multi-user exposure has not been confirmed
- **THEN** the corresponding behavior remains disabled
- **AND** the provider does not assume permission from package availability alone

#### Scenario: Offline fixture is committed

- **WHEN** a FiinQuantX contract fixture is added to Git
- **THEN** it contains synthetic values only
- **AND** reproduces only the reviewed shape needed for tests
- **AND** includes no credential, account, customer, or licensed production record

#### Scenario: Local data service exposes licensed data

- **WHEN** canonical local REST exposure is enabled by policy
- **THEN** the endpoint remains read-only
- **AND** uses canonical contracts and safe metadata
- **AND** does not add broker, account, order, portfolio, transfer, margin, trading, or credential-management endpoints

### Requirement: Provider errors shall remain typed and sanitized

The system SHALL distinguish installation, compatibility, auth, entitlement, quota, rate-limit, schema, invalid-request, empty-result, and provider-runtime outcomes.

#### Scenario: Provider returns no rows successfully

- **WHEN** the SDK returns a valid empty result for the requested symbol/date/market condition
- **THEN** the platform represents a valid empty dataset according to contract policy
- **AND** does not misclassify it as authentication, entitlement, or provider failure

#### Scenario: SDK raises an unexpected exception

- **WHEN** an unexpected SDK exception crosses the adapter boundary
- **THEN** the provider wraps it in a platform provider error
- **AND** records safe internal exception type/correlation metadata
- **AND** returns an allowlisted public message
- **AND** does not expose raw provider payload or credentials

### Requirement: Existing providers and public APIs shall remain backward compatible

The system SHALL add FiinQuantX without removing existing providers or changing established default behavior unless a separate reviewed routing-policy change explicitly does so.

#### Scenario: FiinQuantX is unavailable

- **WHEN** a user runs existing KBS, VCI, DNSE, TCBS, MSN, FMP, or FMARKET workflows without FiinQuantX installed
- **THEN** existing explicit-source behavior remains unchanged
- **AND** existing public APIs remain valid

#### Scenario: Commercial priority is configured

- **WHEN** an operator configures FiinQuantX as preferred for a specific dataset family
- **THEN** auto routing applies that priority only after capability, entitlement, health, quota, freshness, and deployment-policy checks
- **AND** records the reason for selection

### Requirement: Live tests shall be explicit, licensed, and bounded

The system SHALL keep FiinQuantX live tests disabled by default and SHALL require explicit licensed-environment acknowledgement.

#### Scenario: Default CI runs

- **WHEN** normal public/offline CI executes
- **THEN** no FiinQuantX live endpoint is called
- **AND** all provider tests use synthetic fixtures
- **AND** the base package requires no commercial credential

#### Scenario: Licensed live test runs

- **WHEN** `VNSTOCK_LIVE_TESTS=true`, `VNSTOCK_LIVE_PROVIDERS=FIINQUANTX`, and the licensed acknowledgement are set
- **THEN** the test uses a minimal bounded symbol/date request
- **AND** validates canonical columns, safe metadata, entitlement, and quality behavior
- **AND** does not print or persist raw credentials or full licensed payloads

### Requirement: FiinQuantX integration shall remain data-only

The FiinQuantX provider SHALL expose only approved market, reference, ownership, valuation, fundamental, and other research-data retrieval capabilities.

#### Scenario: SDK contains adjacent trading features

- **WHEN** the installed commercial SDK exposes broker, account, portfolio, order, allocation, margin, transfer, execution, recommendation, or automated-trading methods
- **THEN** the FiinQuantX provider does not import, register, route, document, or expose those methods
- **AND** capability and service-boundary tests prevent their addition
- **AND** the **read-only research boundary** remains intact