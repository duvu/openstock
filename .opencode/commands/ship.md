---
description: Commit and push all submodules, then commit and push the workspace root.
model: openai/gpt-5.4-mini
---

Commit, push all submodules, then commit and push the workspace root (`openstock`).

**Optional input**: `$ARGUMENTS` — short description or PR title hint. If omitted, derive from recent changes.

**Steps**

1. Determine which submodules have uncommitted or unpushed changes:
   - `git submodule foreach --recursive 'git status --short'`

2. For each submodule that has changes (iterate in order: `vnstock`, `vnalpha`):
   a. `cd <submodule>` (use the submodule path)
   b. Stage non-ignored files: `git add -A`
      - Never stage `.opencode/`, `.serena/`, `uv.lock`, `*.pyc`, `__pycache__`, `dist/`, `build/`, `.venv/`
   c. Compose a conventional-commit message: `<type>(<scope>): <subject>`
      - Derive from `git diff --cached --stat` or use `$ARGUMENTS` as the subject.
   d. `git commit -m "<message>"` — skip if nothing to commit.
   e. `git push -u origin HEAD` — push the current branch.
   f. If `git commit` or `git push` fails, report the error and stop.

3. Return to the workspace root (`openstock/`).

4. Stage the updated submodule pointers and any root-level files:
   - `git add -A`
   - Never stage `.opencode/`, `.serena/`, `*.pyc`, `__pycache__`.

5. Compose a root commit message summarising which submodules were updated.
   - Format: `chore(workspace): update submodule pointers — <summary>`

6. `git commit -m "<message>"` — skip if nothing to commit.

7. `git push -u origin HEAD` to push the root repo.

8. Report a summary: which submodules were pushed, on which branches, and the root push result.

**Constraints**
- Never force-push in any repo.
- Never commit secrets or files listed in the never-stage list above.
- Process submodules before the root — the root commit must reference the latest submodule SHAs.
- If a submodule push fails, stop and report; do not commit the root with a stale pointer.
- If there is nothing to commit anywhere, say so clearly.
