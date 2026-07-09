# Specification: Assistant Research Intelligence Tools

## ADDED Requirements

### Requirement: Expanded research intelligence intents

The assistant SHALL classify and plan deeper research-intelligence workflows.

#### Scenario: User asks for deep symbol review

- **WHEN** the user asks for a full research review of a symbol
- **THEN** the assistant maps the request to `deep_analyze_symbol` and plans the deterministic analysis tool

### Requirement: Deterministic tool grounding

The assistant SHALL use bounded deterministic tools for research intelligence.

#### Scenario: Assistant answers sector context

- **WHEN** the answer discusses sector strength
- **THEN** the answer is grounded in `sector.get_strength` or equivalent structured output

### Requirement: Research-only policy check

The assistant SHALL reject or rewrite execution-oriented requests.

#### Scenario: User asks for shortlist as buy list

- **WHEN** a prompt implies order, broker, account, allocation, portfolio, margin, or trading execution
- **THEN** the assistant refuses or reframes into research-only output

### Requirement: Groundedness validation

The assistant SHALL validate final research answers against tool outputs.

#### Scenario: Synthesis references a metric

- **WHEN** the answer cites a score, setup, regime, sector, level, or evidence metric
- **THEN** the metric exists in the tool payload or is explicitly marked unavailable

### Requirement: Research answer audit

The assistant SHALL persist answer audit metadata for deep workflows.

#### Scenario: A scenario plan answer is returned

- **WHEN** final answer is produced
- **THEN** audit metadata includes intent, tools, artifact refs, freshness, groundedness result, policy result, caveats, and correlation ID
