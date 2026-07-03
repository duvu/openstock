# Agent Notes for openstock workspace

This directory is a logical container for three independent git repositories.
All active Python development is inside `vnstock/`. See `vnstock/AGENTS.md` for
the full developer guide.

## Workspace Structure

| Directory   | What it is                                                                 |
|-------------|----------------------------------------------------------------------------|
| `vnstock/`  | Primary Python library — Vietnamese financial market data toolkit (v4). Active code, tests, CI. |
| `openspec/` | Spec-driven change management workspace. Contains change proposals, designs, tasks for `vnstock`. Not a Python package. |
| `vnalpha/`  | Docs-only stub (design documents, no runnable code yet).                  |

Each subdirectory is its own `.git` repo. There is no shared root build tool,
lockfile, or workspace config — run all commands from inside `vnstock/`.

## OpenSpec Workflow

`openspec/changes/` holds named change directories. Use the slash commands below
only when the user explicitly requests the spec-driven workflow:

- `/opsx-propose` — draft a new change (proposal + design + tasks)
- `/opsx-apply`   — implement tasks on a `feat/<change-name>` branch
- `/opsx-explore` — think/investigate mode, no code
- `/opsx-archive` — archive a completed change to `openspec/changes/archive/`
