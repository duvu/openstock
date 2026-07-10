from __future__ import annotations

import re
from pathlib import Path
from typing import Final

SOURCE_ROOT: Final = Path(__file__).parents[1] / "src" / "vnalpha"
DOCS_ROOT: Final = Path(__file__).parents[1] / "docs"
GOVERNED_SOURCE_FILES: Final = (
    Path("assistant/executor.py"),
    Path("assistant/planner.py"),
    Path("tools/setup.py"),
    Path("commands/models.py"),
    Path("commands/setup.py"),
)
PHASE_LABEL: Final = re.compile(r"\bPhase\s+\d+(?:\.\d+)*(?:/\d+(?:\.\d+)*)?\b")


def test_core_architecture_descriptions_use_capability_language() -> None:
    # Given: the explicitly governed assistant, tool, and command architecture files
    # When: their prose is scanned for numbered implementation-phase labels
    stale_lines = [
        f"{relative_path}:{line_number}:{line.strip()}"
        for relative_path in GOVERNED_SOURCE_FILES
        for line_number, line in enumerate(
            (SOURCE_ROOT / relative_path).read_text(encoding="utf-8").splitlines(),
            start=1,
        )
        if PHASE_LABEL.search(line)
    ]

    # Then: architecture descriptions remain coupled to capabilities, not project phases
    assert not stale_lines, "\n".join(stale_lines)


def test_architecture_docs_describe_current_package_boundaries() -> None:
    # Given: the architecture refactor's documented package-boundary contract
    # When: its authoritative documents are inspected
    expected_sections = {
        "architecture.md": (
            "cli_app",
            "data.fetch",
            "ensure_symbol_analysis_ready",
            "model routing",
            "workspace_context",
            "commandstatus",
        ),
        "package-boundaries.md": (
            "policy",
            "tui.routing",
            "data_availability",
            "planner",
            "service",
        ),
    }
    documents = {
        filename: (DOCS_ROOT / filename).read_text(encoding="utf-8").lower()
        for filename in expected_sections
    }

    # Then: each required document exists and names its implemented boundaries
    for filename, sections in expected_sections.items():
        assert all(section in documents[filename] for section in sections)
