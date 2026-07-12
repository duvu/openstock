# Deploy gates and promote/rollback reference (legacy)

The closed-loop research-artifact contract in
[`closed-loop-repair.md`](closed-loop-repair.md) is authoritative for current
`repair`, `validate`, and `deploy` behavior.

This page is a compact reference for currently exposed deploy commands.

## Commands

### `vnalpha deploy verify`

```bash
vnalpha deploy verify <candidate> [--deployment-id TEXT] [--json]
```

Behavior:

- `--deployment-id` is optional and auto-generated when omitted.
- `--command` / command override is **not supported** for closed-loop deploy.
- Verifies artifact lineage, schema, boundary, and validation evidence.
- Persists a verification record and emits `DEPLOY_VERIFY_COMPLETED`.
- Exit code is 0 when verification passes, 1 otherwise.

### `vnalpha deploy promote`

```bash
vnalpha deploy promote <candidate> --deployment-id <id> [--previous <previous-candidate>] [--json]
```

Behavior:

- Requires prior verification for the same `<candidate>` and `<deployment-id>`.
- Fails if read-only boundary or evidence checks do not revalidate.
- Persists research artifact deployment state and emits `RESEARCH_ARTIFACT_PROMOTED`.
- Exit code is 0 on success, 1 on gate failure.

### `vnalpha deploy rollback`

```bash
vnalpha deploy rollback <deployment-id> [--reason TEXT] [--json]
```

Behavior:

- Records rollback state and emits `RESEARCH_ARTIFACT_ROLLED_BACK`.
- Exit code is 0 on success, 1 if deployment state is unavailable or not applicable.

## Scope note

Legacy commands listed in older versions, such as `smoke`, `status`, and `list`,
are not exposed through the closed-loop `/deploy` surface.
