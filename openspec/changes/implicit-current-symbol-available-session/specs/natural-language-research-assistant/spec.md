## MODIFIED Requirements

### Requirement: Current-symbol research dates shall use the latest usable completed session

For an omitted date or semantic `today`, current-symbol research SHALL preserve
the request as implicit until readiness selects the latest canonical session on
or before the current configured Vietnam market session where the target and
VNINDEX are aligned and both have the required lookback. It SHALL emit a
bounded freshness warning when that effective session precedes the requested
current session. Feature, score, analysis, audit, and remediation SHALL use
that effective session. An explicit ISO date SHALL remain strict and SHALL NOT
silently fall back.

#### Scenario: Current-session canonical evidence is not available

- **GIVEN** an implicit FPT request on `2026-07-23`
- **AND** FPT and VNINDEX have aligned canonical evidence through `2026-07-22`
- **AND** no candidate score has been built for `2026-07-22`
- **WHEN** readiness runs
- **THEN** it provisions and analyzes `2026-07-22`
- **AND** it reports a bounded current-session freshness warning.

#### Scenario: Explicit unavailable date remains strict

- **GIVEN** an explicit request for `2026-07-23`
- **WHEN** no canonical target bar exists for that date
- **THEN** readiness reports unavailable evidence for `2026-07-23`
- **AND** it does not substitute an earlier session.
