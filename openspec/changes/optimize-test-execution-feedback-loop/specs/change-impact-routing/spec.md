## ADDED Requirements

### Requirement: Repository changes SHALL be classified by impact
The routing policy SHALL classify normalized repository-relative paths as `docs_openspec_only`, `vnalpha`, `vnstock`, `packaging`, `shared_contract` or `test_or_workflow_infrastructure` and SHALL emit the validation lanes required by the complete changed-path set.

#### Scenario: Only documentation and OpenSpec files change
- **WHEN** every changed path belongs to documentation or OpenSpec artifacts
- **THEN** routing selects consistency/spec without runtime suites.

#### Scenario: Application and provider paths change together
- **WHEN** paths classify as both `vnalpha` and `vnstock`
- **THEN** routing selects both owning domains plus consistency and fast smoke.

### Requirement: Unknown paths SHALL fail closed
No unknown path SHALL be classified as docs-only or silently omitted. Routing, test manifests, migrations, shared fixtures, pytest configuration, Make targets and workflow changes SHALL trigger full appropriate regression.

#### Scenario: An unrecognized top-level path changes
- **WHEN** the path classifier has no matching rule
- **THEN** it exits non-zero and identifies the unknown path.

#### Scenario: Test infrastructure changes
- **WHEN** a suite manifest, shared fixture, migration, pytest option, runner, Make target or workflow changes
- **THEN** full regression is required in addition to consistency.

### Requirement: Affected domains SHALL run independently
When smoke, affected-domain and full/package lanes are all required, independent jobs SHALL be eligible to run in parallel and SHALL preserve separate logs and conclusions.

#### Scenario: Shared test infrastructure changes
- **WHEN** routing requires smoke, all domains and full regression
- **THEN** the workflow exposes independent jobs without a sequential smoke-to-full dependency.

### Requirement: Routing policy SHALL be machine tested
The classifier SHALL have positive and negative tests for every path class, mixed changes, unknown paths and infrastructure escalation. Workflow consumers SHALL use the classifier outputs rather than duplicating path policy in expressions.

#### Scenario: A routing rule regresses
- **WHEN** a known infrastructure path no longer selects full regression
- **THEN** the classifier contract test fails before workflow publication.
