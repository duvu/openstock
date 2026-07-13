from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

from vnalpha.sandbox.docker_policy import DockerImageReference
from vnalpha.sandbox.models import SandboxJob

JsonValue: TypeAlias = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


@dataclass(frozen=True, slots=True)
class SandboxGeneratedProgram:
    code: str
    summary: str
    input_references: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SandboxPreview:
    job: SandboxJob
    code_summary: str
    image: DockerImageReference

    @property
    def arguments(self) -> dict[str, JsonValue]:
        return {
            "purpose": self.job.purpose,
            "job_id": str(self.job.job_id),
            "run_id": str(self.job.run_id),
            "correlation_id": str(self.job.correlation_id),
            "code_summary": self.code_summary,
            "code_digest": self.job.code_digest,
            "input_references": list(self.job.filesystem_policy.approved_read_paths),
            "resource_limits": {
                "cpu_millis": self.job.resource_limits.cpu_millis,
                "memory_mb": self.job.resource_limits.memory_mb,
                "timeout_seconds": self.job.resource_limits.timeout_seconds,
            },
            "image": str(self.image),
            "image_digest": str(self.image).split("@", 1)[1],
        }
