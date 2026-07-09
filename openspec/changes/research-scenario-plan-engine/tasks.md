# Tasks: Research Scenario Plan Engine

## 0. Governance

- [ ] 0.1 Keep scenario plans research-only.
- [ ] 0.2 Do not include order, broker, account, portfolio, allocation, margin, or execution actions.
- [ ] 0.3 Run policy wording validation before final rendering.

## 1. Models and persistence

- [ ] 1.1 Add or reuse `ResearchScenarioPlan` model.
- [ ] 1.2 Persist scenario plan records.
- [ ] 1.3 Link plan to deep analysis, level snapshot, evidence snapshot, and correlation ID.

## 2. Builder

- [ ] 2.1 Build current setup summary.
- [ ] 2.2 Attach key levels.
- [ ] 2.3 Generate confirmation conditions.
- [ ] 2.4 Generate invalidation conditions.
- [ ] 2.5 Generate scenario tree.
- [ ] 2.6 Generate checklist.
- [ ] 2.7 Attach confidence and caveats.

## 3. Policy validation

- [ ] 3.1 Add scenario language validator.
- [ ] 3.2 Reject execution wording.
- [ ] 3.3 Require research-only disclaimer.
- [ ] 3.4 Add tests for allowed and denied phrasing.

## 4. Commands and assistant

- [ ] 4.1 Add `/research-plan SYMBOL`.
- [ ] 4.2 Add `scenario.generate_research_plan` tool.
- [ ] 4.3 Add assistant intent `generate_research_scenario`.
- [ ] 4.4 Add synthesis template.

## 5. Tests and validation

- [ ] 5.1 Test plan includes required fields.
- [ ] 5.2 Test missing level data caveat.
- [ ] 5.3 Test policy rejection for execution wording.
- [ ] 5.4 Run standard validation commands and attach evidence.
