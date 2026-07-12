# Assistant lifecycle hardening

The assistant accepts an `AssistantRequest` with four separate fields:

- `current_user_prompt`: the only field used by deterministic safety checks and intent classification.
- `workspace_context` and `chat_context`: bounded historical reference data.
- `date`: explicit request metadata.

Historical context is sent in a separate message marked untrusted and potentially stale. Instructions inside it are not executable. Current warehouse and deterministic tool output remains authoritative.

## Prepared turns

`AssistantApp.prepare()` performs safety, classification, policy checks, normalization, and plan construction once. It persists a canonical plan and SHA-256 identity in `prepared_assistant_turn`. `execute_prepared()` verifies that identity and executes the exact plan without reclassifying or replanning. `ask()` remains the compatibility wrapper.

The TUI uses the prepared object for plan-only, approval, and automatic safe-tool modes. Approval executes the stored plan; cancellation marks it cancelled. A hash mismatch fails closed.

## Prompt persistence

By default, assistant sessions store a bounded summary, SHA-256 hash, character count, and context references. The full current request is redacted and stored only when `VNALPHA_ASSISTANT_STORE_RAW=true`; workspace and chat bodies are never duplicated into the prompt row.

## Workspace hooks and recovery

TUI workspace recording is best effort. A recording or refresh failure renders a warning and cannot prevent a command or chat turn from running. Startup validates the canonical workspace, quarantines malformed latest/state files, and creates a temporary recovery workspace when the canonical root is unavailable. `/context repair --dry-run` reports malformed files; `/context repair` applies quarantine and recovery.
