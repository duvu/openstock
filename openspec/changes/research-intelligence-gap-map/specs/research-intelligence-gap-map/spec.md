# Specification: Research intelligence gap map

## ADDED Requirements

### Requirement: Gap map document shall exist

The repository SHALL include a research intelligence gap map document.

#### Scenario: Gap map document is present

- **GIVEN** the OpenSpec change is implemented
- **WHEN** repository docs are inspected
- **THEN** `vnalpha/docs/research-intelligence-gap-map.md` SHALL exist.

#### Scenario: Gap map document states planning-only scope

- **GIVEN** the document is opened
- **WHEN** the scope section is reviewed
- **THEN** it SHALL state that this change is a planning and gap-assessment artifact, not a runtime implementation.

---

### Requirement: Current capability inventory shall be documented

The gap map SHALL inventory current system capabilities before defining future work.

#### Scenario: Data capabilities are inventoried

- **GIVEN** the gap map document is reviewed
- **WHEN** the current capability section is inspected
- **THEN** it SHALL list ingestion, warehouse, feature, scoring, watchlist, assistant, TUI, and observability capabilities.

#### Scenario: Current limits are documented

- **GIVEN** the gap map document is reviewed
- **WHEN** the current capability section is inspected
- **THEN** it SHALL explain that current intelligence is mainly score-based screening and basic explain/compare.

---

### Requirement: Target research capability model shall be documented

The gap map SHALL define the target capabilities needed for a research decision-support workflow.

#### Scenario: Deep symbol analysis target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for deep symbol analysis.

#### Scenario: Market and sector context target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for market regime and sector context.

#### Scenario: Watchlist synthesis target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for watchlist synthesis.

#### Scenario: Shortlist target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for shortlist generation.

#### Scenario: Conditional research scenario target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for conditional research scenario planning.

#### Scenario: Historical evidence target is defined

- **GIVEN** the target capability model is reviewed
- **THEN** it SHALL define the expected output for historical setup evidence.

---

### Requirement: Formal gap matrix shall be included

The gap map SHALL include a matrix comparing current state to target state.

#### Scenario: Gap matrix has required columns

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include columns for capability, current state, target state, gap, priority, future OpenSpec, and acceptance evidence.

#### Scenario: Deep analysis gap is listed

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include a row for deep symbol analysis.

#### Scenario: Watchlist synthesis gap is listed

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include a row for watchlist synthesis.

#### Scenario: Shortlist gap is listed

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include a row for shortlist generation.

#### Scenario: Scenario planning gap is listed

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include a row for conditional research scenario planning.

#### Scenario: Historical evidence gap is listed

- **GIVEN** the gap matrix is reviewed
- **THEN** it SHALL include a row for historical evidence.

---

### Requirement: Data and schema gaps shall be listed

The gap map SHALL identify required future data artifacts.

#### Scenario: Market regime schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for market regime snapshots.

#### Scenario: Sector strength schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for sector strength snapshots.

#### Scenario: Symbol level schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for symbol level snapshots.

#### Scenario: Shortlist schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for shortlist candidate records.

#### Scenario: Scenario plan schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for research scenario plan records.

#### Scenario: Historical evidence schema gap is listed

- **GIVEN** the data/schema section is reviewed
- **THEN** it SHALL identify the need for setup historical evidence records.

---

### Requirement: Command and API gaps shall be listed

The gap map SHALL define missing commands and tool contracts.

#### Scenario: Analyze command gap is listed

- **GIVEN** the command/API section is reviewed
- **THEN** it SHALL identify a missing `/analyze SYMBOL` command or equivalent.

#### Scenario: Shortlist command gap is listed

- **GIVEN** the command/API section is reviewed
- **THEN** it SHALL identify a missing `/shortlist` command or equivalent.

#### Scenario: Research plan command gap is listed

- **GIVEN** the command/API section is reviewed
- **THEN** it SHALL identify a missing `/research-plan SYMBOL` command or equivalent.

#### Scenario: Historical evidence command gap is listed

- **GIVEN** the command/API section is reviewed
- **THEN** it SHALL identify a missing `/setup-evidence` command or equivalent.

---

### Requirement: Assistant gaps shall be listed

The gap map SHALL define missing assistant intents, tools, and synthesis templates.

#### Scenario: Deep analysis intent gap is listed

- **GIVEN** the assistant gap section is reviewed
- **THEN** it SHALL identify a missing `deep_analyze_symbol` intent or equivalent.

#### Scenario: Shortlist intent gap is listed

- **GIVEN** the assistant gap section is reviewed
- **THEN** it SHALL identify a missing `generate_shortlist` intent or equivalent.

#### Scenario: Scenario intent gap is listed

- **GIVEN** the assistant gap section is reviewed
- **THEN** it SHALL identify a missing conditional research scenario intent or equivalent.

#### Scenario: Historical evidence intent gap is listed

- **GIVEN** the assistant gap section is reviewed
- **THEN** it SHALL identify a missing setup evidence intent or equivalent.

---

### Requirement: Policy guardrails shall be explicit

The gap map SHALL distinguish allowed research outputs from disallowed execution-oriented outputs.

#### Scenario: Allowed research content is defined

- **GIVEN** the policy section is reviewed
- **THEN** it SHALL permit conditional scenarios, setup analysis, key levels, risk/reward estimates, checklists, caveats, and confidence statements when grounded in data.

#### Scenario: Disallowed content is defined

- **GIVEN** the policy section is reviewed
- **THEN** it SHALL disallow account-specific advice, allocation instructions, external platform actions, certainty claims, and execution-oriented commands.

---

### Requirement: Future OpenSpec split shall be defined

The gap map SHALL define future implementation OpenSpecs.

#### Scenario: Deep analysis OpenSpec is listed

- **GIVEN** the roadmap is reviewed
- **THEN** `deep-symbol-analysis-engine` SHALL be listed as a future OpenSpec.

#### Scenario: Market context OpenSpec is listed

- **GIVEN** the roadmap is reviewed
- **THEN** `market-regime-and-sector-context` SHALL be listed as a future OpenSpec.

#### Scenario: Watchlist and shortlist OpenSpec is listed

- **GIVEN** the roadmap is reviewed
- **THEN** `watchlist-synthesis-and-shortlist` SHALL be listed as a future OpenSpec.

#### Scenario: Scenario plan OpenSpec is listed

- **GIVEN** the roadmap is reviewed
- **THEN** `research-scenario-plan-engine` SHALL be listed as a future OpenSpec.

#### Scenario: Historical evidence OpenSpec is listed

- **GIVEN** the roadmap is reviewed
- **THEN** `setup-historical-evidence-engine` SHALL be listed as a future OpenSpec.

---

### Requirement: Evaluation gaps shall be defined

The gap map SHALL define missing evaluation artifacts and quality checks.

#### Scenario: Golden set gaps are listed

- **GIVEN** the evaluation section is reviewed
- **THEN** it SHALL list research answer, shortlist, scenario plan, and policy-safety golden sets.

#### Scenario: Quality checks are listed

- **GIVEN** the evaluation section is reviewed
- **THEN** it SHALL list groundedness, caveat coverage, missing-data handling, policy-safety, and usefulness checks.

---

### Requirement: This change shall not claim runtime implementation

The gap-map OpenSpec SHALL not mark runtime engine work complete.

#### Scenario: Runtime work remains future work

- **GIVEN** tasks are reviewed
- **WHEN** this gap-map change is merged
- **THEN** no deep analysis, shortlist, scenario planning, or historical evidence runtime implementation SHALL be claimed as complete.
