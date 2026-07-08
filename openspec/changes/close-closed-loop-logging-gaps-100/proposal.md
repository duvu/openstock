# Proposal: Close closed-loop logging and AI repair gaps to 100%

## Summary

Create a focused OpenSpec change to close the remaining implementation gaps between the current file-based observability layer and the target closed-loop improvement workflow.

Target workflow:

```text
RUN -> OBSERVE -> PACKAGE -> AI FIX -> VALIDATE -> PROMOTE/REJECT -> DEPLOY LOG -> REPEAT
```

This change is intentionally an OpenSpec-only planning artifact. It defines the runtime requirements, evidence gates, and acceptance criteria needed before OpenStock can claim the closed-loop logging and AI-assisted repair workflow is complete.

## Current state

The codebase already has a meaningful file-based observability foundation:

```text
RunContext and run directories
JSONL writer
redaction helper
audit/app/error/trace/command writers
ai-agent-summary.md generation
logs bundle tar.gz
vnalpha logs latest/show/errors/summarize/doctor/bundle
some ChatController / AssistantApp / tool / domain instrumentation
some shell-script JSONL logging
```

However, the implementation is not yet a closed-loop improvement system. The remaining gaps are functional, not cosmetic.

## Problem statement

The current implementation can create log artifacts for AI review, but it does not yet reliably support the complete repair loop:

```text
runtime failure
  -> correlated logs
  -> AI coding repair bundle
  -> repair branch/PR tracking
  -> validation gate
  -> deploy promote/reject decision
  -> rollback path
  -> deploy result logged
```

Several existing issues also reduce log reliability:

- CLI and observability use separate correlation ID ContextVars.
- Some `log_audit()` call sites pass unsupported parameters, causing events to be swallowed.
- Typer commands are not uniformly wrapped with command lifecycle logging.
- Pipeline and verify scripts log only coarse start/end events, not step/check events.
- Backup failure paths can exit before writing failure events.
- There is no `repair` command group.
- There is no AI coding repair bundle with `ai-coding-prompt.md`, `reproduction.md`, and rich manifest.
- There is no deploy gate, promote command, rollback command, or deploy event lifecycle.
- There is no end-to-end fixture proving failure -> logs -> repair bundle -> validation -> deploy gate.

## Goals

- Make all runtime observability events share one non-`unset` correlation ID.
- Ensure all audit call sites write actual events instead of being swallowed by parameter mismatch.
- Wrap major CLI commands with command lifecycle logging.
- Log pipeline steps and verify checks as structured JSONL events.
- Log backup success and all backup failure paths.
- Generate an AI coding repair bundle from latest logs.
- Track repair status, branch, PR, commits, validation commands, and validation results.
- Add deploy verify/promote/rollback skeletons with strict gates.
- Block promotion when validation is missing or failed, unless a documented explicit override is provided.
- Log deploy verify, promotion, block, post-deploy smoke, and rollback outcomes.
- Add automated tests and dry-run scenarios for the loop.
- Keep safety boundaries intact: no broker/order/account/portfolio/margin/trading execution features.

## Non-goals

- No autonomous production deployment without a gate.
- No self-modifying runtime process.
- No automatic merge to `main` without review.
- No cloud CI/CD dependency in the first implementation.
- No external log collector requirement.
- No bypass of tests, lint, verify, smoke, deploy verification, or rollback checks.
- No trading execution surface of any kind.

## Proposed change

Add a new implementation-focused OpenSpec change that requires these capability groups:

```text
1. Correlation unification
2. Audit writer compatibility and call-site hardening
3. CLI command lifecycle wrapper
4. Script-level step/check/failure logging
5. Repair bundle generation
6. Repair status and validation tracking
7. Deploy verify/promote/rollback gate
8. End-to-end closed-loop fixture
9. Evidence-backed completion matrix
```

## Success criteria

The change can be considered complete only when all of the following are true:

```text
- All major command/audit/error/trace events share a non-unset correlation ID.
- TOOL_REFUSED, CHAT_REFUSAL, ASSISTANT_ANSWER_LOGGED, and command events are actually written.
- Major Typer commands emit COMMAND_STARTED / COMMAND_SUCCEEDED / COMMAND_FAILED.
- Pipeline script emits step-level JSONL events.
- openstock-verify emits check-level JSONL events.
- backup script logs lock/missing-file/copy failure and success paths.
- vnalpha repair prepare --latest generates a repair bundle.
- repair bundle includes ai-coding-prompt.md, reproduction.md, manifest.json, environment.json, selected raw logs, required validation commands, and guardrails.
- vnalpha repair status <repair-id> works.
- vnalpha repair validate <repair-id> records validation commands and results.
- vnalpha deploy verify records previous/candidate versions and gate status.
- vnalpha deploy promote <candidate> is blocked when validation is missing/failed.
- vnalpha deploy rollback <deployment-id> records rollback attempt/result.
- Closed-loop fixture proves failed command -> logs -> repair bundle -> validation gate.
- Tests and validation evidence are committed.
```

## Completion principle

Do not mark this change complete because APIs or helper functions exist. Completion requires end-to-end evidence that runtime events are written, repair bundles are generated, validation is enforced, deploy promotion is gated, and outcomes are logged.
