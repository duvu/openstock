# Capability: assistant LLM preflight

## ADDED Requirements

### Requirement: Bounded typed LLM route preflight

The application SHALL provide a bounded assistant preflight that verifies one
MVP1 model route and returns a typed result distinguishing missing
configuration, missing credentials, missing model/routing configuration, an
unreachable gateway, an authentication failure, a model not found on the
gateway, and unsupported structured output. The probe SHALL be bounded and
SHALL NOT require a live provider call in automated tests.

#### Scenario: Missing configuration is typed before any probe
- **GIVEN** no endpoint/model configured
- **WHEN** the preflight runs
- **THEN** it returns `missing_config` without performing a network probe.

#### Scenario: Distinct failure modes are typed
- **WHEN** the probe fails with a timeout, HTTP 401/403, HTTP 404, or a
  structured-output rejection
- **THEN** the preflight returns `unreachable_gateway`, `auth_failed`,
  `model_not_found`, and `unsupported_structured_output` respectively.

#### Scenario: A single-model transport failure is not masked
- **GIVEN** a single-model route whose primary call failed on transport
- **WHEN** the gateway reports no compatible fallback
- **THEN** the preflight reports `unreachable_gateway`, not a structured-output
  gap.

### Requirement: Successful route identity without secret leakage

On success the preflight SHALL report the actual model route identity, and its
status view SHALL never contain secrets or prompt content.

#### Scenario: Ready records route identity
- **GIVEN** a verified route
- **WHEN** the preflight succeeds
- **THEN** the result is `ready` and includes the route model id.

#### Scenario: Status view is redaction-safe
- **WHEN** the preflight status dict is produced
- **THEN** it contains no API key and no prompt content.

### Requirement: Degraded mode keeps deterministic commands usable

When the preflight is not ready, the CLI SHALL exit non-zero for the preflight
command and clearly state that natural-language chat is unavailable while
deterministic slash and data commands remain usable.

#### Scenario: Preflight command fails closed with guidance
- **GIVEN** an unavailable LLM route
- **WHEN** `vnalpha preflight` runs
- **THEN** it exits non-zero and states deterministic commands remain usable.

#### Scenario: ask reports degraded mode
- **GIVEN** an unconfigured LLM route
- **WHEN** `vnalpha ask` runs
- **THEN** it reports natural-language chat is unavailable and points to
  `vnalpha preflight`.
