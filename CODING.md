# OpenStock coding conventions

This file is the normative coding-style source for OpenStock. Keep conventions simple, conventional and enforceable with Ruff. Do not duplicate the full policy in issues or implementation notes.

## 1. Imports

All imports MUST be declared at module scope at the top of the file, immediately after the module docstring and any `from __future__` import.

Required order, with one blank line between groups:

```python
"""Module purpose."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
from pydantic import BaseModel

from vnalpha.domain.models import ResearchResult
from vnalpha.infrastructure.warehouse import Warehouse
```

Rules:

- no imports inside functions, methods, classes, loops, conditions or exception handlers;
- no imports after constants, models, functions or executable statements;
- no wildcard imports;
- prefer absolute project imports;
- remove unused imports;
- import order is standard library, third-party, then project-local;
- do not hide circular dependencies with local imports: move shared types to a lower-level module, introduce a protocol, or correct the dependency direction;
- optional dependencies belong behind a dedicated adapter; use top-level `importlib` when dynamic loading is genuinely required.

## 2. File structure

Use this order:

```text
module docstring
future imports
imports
constants
public types/models
public functions/classes
private helpers
```

Do not interleave imports, constants, classes and executable initialization.

## 3. Formatting and naming

Ruff is the formatter and linter. Do not hand-format around it.

```text
line length: 88
indentation: 4 spaces
quotes: double
modules/functions/variables: snake_case
classes: PascalCase
constants: UPPER_SNAKE_CASE
private symbols: _leading_underscore
```

Choose names that express the domain. Avoid vague names such as `data`, `obj`, `manager`, `helper`, `utils`, `temp` or numbered variants when a specific name is available.

## 4. Types and models

- Public functions, methods and application/provider/repository boundaries require explicit type annotations.
- Prefer dataclasses, enums and Pydantic boundary models over free-form dictionaries and magic strings.
- Avoid `Any` when a stable domain type can be expressed.
- Keep requested date, effective market date, publication time and generated time as distinct typed fields.

## 5. Functions and dependencies

- A function should perform one clear responsibility.
- Prefer early returns over deeply nested control flow.
- Do not combine database access, provider calls, domain calculation and presentation in one function.
- Dependency direction is presentation/adapters → application → domain contracts → infrastructure adapters.
- Application/domain code must not import CLI, TUI or assistant presentation modules.
- Avoid mutable module-level runtime state.
- Avoid generic `utils.py`, `helpers.py`, `common.py` and `misc.py`; name modules after their responsibility.

## 6. Errors and logging

- Catch specific exceptions close to the boundary that can handle them.
- Broad `Exception` catches are allowed only at top-level process boundaries such as CLI commands, workers, HTTP handlers or assistant tools.
- Never silently swallow an exception.
- Use typed public failures and preserve the original exception with `raise ... from exc`.
- Use logging in application/library code; do not leave `print()` or temporary debug output.

## 7. Comments and documentation

- Comments explain intent, invariants and non-obvious constraints, not syntax.
- Public APIs and non-obvious modules should have concise docstrings.
- Private helpers do not require ceremonial docstrings.
- Delete stale comments and temporary diagnostics when implementation is complete.

## 8. Tests

[`TESTING.md`](TESTING.md) is the normative testing policy. Do not proliferate tests, test private helpers or duplicate behavior across layers.

## 9. Agent workflow

For every changed Python file, agents MUST run the focused coding check:

```bash
make lint-files PROJECT=vnalpha FILES="src/path/file.py tests/path/test_file.py"
```

Use `PROJECT=vnstock` for vnstock paths. The command checks formatting, import placement/order, unused imports and wildcard imports only on touched files.

An agent MUST NOT complete work with:

- a function-local, class-local or mid-file import;
- a new wildcard or unused import;
- a circular dependency hidden by deferred import;
- formatting failures in touched files.
