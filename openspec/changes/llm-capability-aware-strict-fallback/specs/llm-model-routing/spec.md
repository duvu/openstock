## MODIFIED Requirements

### Requirement: Explicit model capabilities

OpenStock SHALL load model capabilities only from explicit per-profile
configuration and SHALL include those capabilities in route decisions and
operator status surfaces.

#### Scenario: Capability is not declared

- **WHEN** a profile does not explicitly declare `json_schema`
- **THEN** it is treated as unsupported for strict-schema fallback
- **AND** no provider/model-name inference is performed

### Requirement: Strict-schema compatible fallback

OpenStock SHALL attempt the primary route and then only distinct configured
fallback routes that explicitly support the required strict-schema capability.

#### Scenario: First fallback is unverified and second is verified

- **WHEN** the primary strict route fails
- **AND** the first configured fallback lacks `json_schema`
- **AND** the next distinct fallback declares `json_schema`
- **THEN** the unverified route is not called
- **AND** the verified route is attempted

#### Scenario: Duplicate model IDs are configured

- **WHEN** a compatible fallback resolves to a model ID already attempted
- **THEN** the duplicate route is skipped

### Requirement: Truthful strict fallback failure

OpenStock SHALL raise a typed error when a failed strict primary route has no
verified compatible fallback.

#### Scenario: No compatible fallback exists

- **WHEN** the primary route fails
- **AND** no distinct configured fallback declares `json_schema`
- **THEN** the gateway raises `LLMNoCompatibleFallbackError`
- **AND** exposes error code `no_compatible_fallback`
- **AND** preserves the primary failure as the exception cause

### Requirement: Bounded schema compatibility

OpenStock SHALL preserve at most one schema-format compatibility downgrade per
attempted model route without increasing the configured transport retry budget.

#### Scenario: Endpoint rejects strict schema format

- **WHEN** an attempted route explicitly rejects `json_schema`
- **THEN** that route may retry once with `json_object`
- **AND** no additional transport retry allowance is created

### Requirement: Code and documentation consistency

OpenStock SHALL update runtime, status surfaces, configuration templates,
documentation, OpenSpec and required CI together when model-routing capability
contracts change.
