## ADDED Requirements

### Requirement: Stable required-check visibility

OpenStock SHALL create the complete `openstock-ci` validation surface for every
pull request and every push to `main` without path filters that can omit required
checks.

#### Scenario: Documentation-only pull request

- **WHEN** a pull request changes only documentation or roadmap files
- **THEN** all required `openstock-ci` jobs are still created
- **AND** branch protection can evaluate the same stable check names

### Requirement: Aggregate merge gate

OpenStock SHALL provide an always-evaluated aggregate gate that succeeds only
when repository consistency, `vnalpha`, and `vnstock` validation jobs all
conclude with `success`.

#### Scenario: Component job fails or is skipped

- **WHEN** any component validation job is failed, cancelled or skipped
- **THEN** `openstock-ci / Required merge gate` fails

### Requirement: Current branch-protection documentation

OpenStock SHALL document the exact current required checks, up-to-date branch
requirement, bypass policy and administrator verification evidence.

#### Scenario: Workflow job name changes

- **WHEN** a required workflow or job name changes
- **THEN** workflow, consistency checker, checker tests, documentation and
  OpenSpec are updated together

### Requirement: External settings evidence

OpenStock SHALL NOT claim that branch protection is active until a repository
administrator records evidence from the live GitHub branch/ruleset settings.

#### Scenario: Code-side merge gate is complete

- **WHEN** the workflow and repository checks are implemented and green
- **BUT** the live ruleset has not been verified
- **THEN** issue #147 and its OpenSpec administrator-verification task remain open

### Requirement: Auditable emergency bypass

OpenStock SHALL treat a merge bypass as an exceptional incident requiring an
owner, reason, exact SHA, rollback plan and complete post-merge validation.
