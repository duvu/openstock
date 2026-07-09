# Tasks: Closed-loop repair and validation for auto research

## 0. Governance

- [ ] 0.1 Keep the system inside the read-only research boundary.
- [ ] 0.2 Do not introduce broker, order, account, portfolio, margin, transfer, allocation, or trading execution capabilities.
- [ ] 0.3 Treat `/deploy` as research artifact promotion/rollback only.
- [ ] 0.4 Preserve redaction-by-default logging.
- [ ] 0.5 Preserve validation evidence before promotion.
- [ ] 0.6 Bound all auto-repair loops with max attempts and terminal failure state.

## 1. Closed-loop lifecycle

- [ ] 1.1 Define canonical states: `RUN`, `OBSERVE`, `PACKAGE`, `AI_FIX`, `VALIDATE`, `PROMOTE_READY`, `PROMOTED`, `REJECTED`, `ROLLED_BACK`, `FAILED`.
- [ ] 1.2 Add lifecycle state persistence.
- [ ] 1.3 Link lifecycle state to correlation ID.
- [ ] 1.4 Link lifecycle state to sandbox job / research experiment / feature / hypothesis / pattern artifact IDs.
- [ ] 1.5 Add terminal failure handling.

## 2. Repair bundle

- [ ] 2.1 Add `RepairBundle` model or equivalent.
- [ ] 2.2 Include repair ID.
- [ ] 2.3 Include correlation ID.
- [ ] 2.4 Include failed job/session ID.
- [ ] 2.5 Include user request and plan summary.
- [ ] 2.6 Include generated code.
- [ ] 2.7 Include static guard result.
- [ ] 2.8 Include stdout/stderr.
- [ ] 2.9 Include error trace.
- [ ] 2.10 Include input dataset references.
- [ ] 2.11 Include artifact manifest/output state.
- [ ] 2.12 Include validation result.
- [ ] 2.13 Include environment summary.
- [ ] 2.14 Include redaction status.

## 3. Repair commands

- [ ] 3.1 Implement or bridge `/repair prepare --latest`.
- [ ] 3.2 Implement or bridge `/repair prepare <job-id>`.
- [ ] 3.3 Implement or bridge `/repair status <repair-id>`.
- [ ] 3.4 Implement or bridge `/repair propose <repair-id>`.
- [ ] 3.5 Implement or bridge `/repair apply <repair-id> --attempt <n>` for sandbox research artifacts only.
- [ ] 3.6 Render unsupported repair subcommands inline.
- [ ] 3.7 Emit command lifecycle events.

## 4. AI repair proposal

- [ ] 4.1 Generate repair proposal from repair bundle.
- [ ] 4.2 Limit repair proposal scope to sandbox research code, experiment definitions, feature definitions, or validation schemas.
- [ ] 4.3 Include explanation of the suspected failure cause.
- [ ] 4.4 Include proposed patch/diff or replacement generated code.
- [ ] 4.5 Include expected validation checks.
- [ ] 4.6 Reject repair proposals that include broker/order/account/portfolio/margin/trading execution behavior.

## 5. Bounded repair loop

- [ ] 5.1 Add max repair attempts configuration.
- [ ] 5.2 Re-run repaired job only inside sandbox.
- [ ] 5.3 Persist every repair attempt.
- [ ] 5.4 Capture stdout/stderr/error for every attempt.
- [ ] 5.5 Stop after max attempts.
- [ ] 5.6 Mark repair as failed when attempts are exhausted.

## 6. Validation gate

- [ ] 6.1 Add `/validate run <artifact-id>`.
- [ ] 6.2 Validate static guard pass.
- [ ] 6.3 Validate sandbox execution pass.
- [ ] 6.4 Validate output schema pass.
- [ ] 6.5 Validate artifact manifest pass.
- [ ] 6.6 Validate lineage present.
- [ ] 6.7 Validate quality status present.
- [ ] 6.8 Validate caveats present.
- [ ] 6.9 Validate read-only boundary pass.
- [ ] 6.10 Persist validation report.

## 7. Research artifact promotion

- [ ] 7.1 Define promotable research artifact types.
- [ ] 7.2 Add `/deploy verify <candidate>` for research artifact readiness.
- [ ] 7.3 Add `/deploy promote <candidate> --deployment-id <id>` for research artifact promotion only.
- [ ] 7.4 Add `/deploy rollback <deployment-id>` for research artifact rollback only.
- [ ] 7.5 Persist deploy log.
- [ ] 7.6 Prevent promotion if validation gate fails.
- [ ] 7.7 Prevent promotion if read-only boundary check fails.

## 8. Observability

- [ ] 8.1 Emit `REPAIR_BUNDLE_CREATED`.
- [ ] 8.2 Emit `REPAIR_PROPOSAL_CREATED`.
- [ ] 8.3 Emit `REPAIR_ATTEMPT_STARTED`.
- [ ] 8.4 Emit `REPAIR_ATTEMPT_SUCCEEDED`.
- [ ] 8.5 Emit `REPAIR_ATTEMPT_FAILED`.
- [ ] 8.6 Emit `VALIDATION_STARTED`.
- [ ] 8.7 Emit `VALIDATION_SUCCEEDED`.
- [ ] 8.8 Emit `VALIDATION_FAILED`.
- [ ] 8.9 Emit `RESEARCH_ARTIFACT_PROMOTED`.
- [ ] 8.10 Emit `RESEARCH_ARTIFACT_ROLLED_BACK`.
- [ ] 8.11 Link all events by correlation ID.
- [ ] 8.12 Preserve redaction-by-default.

## 9. Tests

- [ ] 9.1 Test `/repair prepare --latest` packages latest failure.
- [ ] 9.2 Test repair bundle contains required sections.
- [ ] 9.3 Test repair proposal rejects trading-execution content.
- [ ] 9.4 Test repair loop stops at max attempts.
- [ ] 9.5 Test repaired job reruns only inside sandbox.
- [ ] 9.6 Test `/validate run <artifact-id>` passes valid artifact.
- [ ] 9.7 Test validation fails missing lineage.
- [ ] 9.8 Test validation fails missing caveats.
- [ ] 9.9 Test `/deploy verify` requires validation evidence.
- [ ] 9.10 Test `/deploy promote` promotes only research artifact.
- [ ] 9.11 Test `/deploy rollback` records rollback.
- [ ] 9.12 Test read-only boundary blocks execution-like deploy requests.

## 10. Documentation and validation

- [ ] 10.1 Add closed-loop repair architecture doc.
- [ ] 10.2 Document repair bundle schema.
- [ ] 10.3 Document validation gate.
- [ ] 10.4 Document deploy log semantics for research artifacts.
- [ ] 10.5 Document read-only research boundary for repair/deploy.
- [ ] 10.6 Run `make test-vnalpha`.
- [ ] 10.7 Run `make lint-vnalpha`.
- [ ] 10.8 Run `make verify-r4`.
- [ ] 10.9 Run `openstock-verify --ci`.
- [ ] 10.10 Attach validation evidence to PR.
