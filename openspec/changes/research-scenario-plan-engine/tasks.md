# Tasks: Research Scenario Plan Engine

## 0. Governance

- [x] 0.1 Keep scenario plans research-only.
- [x] 0.2 Do not include order, broker, account, portfolio, allocation, margin, or execution actions.
- [x] 0.3 Run policy wording validation before final rendering.

## 1. Models and persistence

- [x] 1.1 Add or reuse `ResearchScenarioPlan` model.
- [x] 1.2 Persist scenario plan records.
- [x] 1.3 Link plan to deep analysis, level snapshot, evidence snapshot, and correlation ID.

## 2. Builder

- [x] 2.1 Build current setup summary.
- [x] 2.2 Attach key levels.
- [x] 2.3 Generate confirmation conditions.
- [x] 2.4 Generate invalidation conditions.
- [x] 2.5 Generate scenario tree.
- [x] 2.6 Generate checklist.
- [x] 2.7 Attach confidence and caveats.

## 3. Policy validation

- [x] 3.1 Add scenario language validator.
- [x] 3.2 Reject execution wording.
- [x] 3.3 Require research-only disclaimer.
- [x] 3.4 Add tests for allowed and denied phrasing.

## 4. Commands and assistant

- [x] 4.1 Add `/research-plan SYMBOL`.
- [x] 4.2 Add `scenario.generate_research_plan` tool.
- [x] 4.3 Add assistant intent `generate_research_scenario`.
- [x] 4.4 Add synthesis template.

## 5. Tests and validation

- [x] 5.1 Test plan includes required fields.
- [x] 5.2 Test missing level data caveat.
- [x] 5.3 Test policy rejection for execution wording.
- [x] 5.4 Run standard validation commands and attach evidence.
