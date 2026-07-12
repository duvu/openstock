from __future__ import annotations

from typing import Protocol

from vnalpha.closed_loop.models import (
    RepairBundle,
    RepairProposal,
    SandboxAttemptResult,
)


class SandboxRepairRunner(Protocol):
    is_sandbox: bool

    def run(
        self, bundle: RepairBundle, proposal: RepairProposal, attempt: int
    ) -> SandboxAttemptResult: ...
