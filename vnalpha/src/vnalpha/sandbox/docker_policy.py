"""Docker sandbox policy values and hardened command construction."""

from __future__ import annotations

import re
import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Final, NewType, final

from typing_extensions import override

from vnalpha.sandbox.models import SandboxResourceLimits

DockerContainerName = NewType("DockerContainerName", str)
DockerImageReference = NewType("DockerImageReference", str)

_CONTAINER_CODE_PATH: Final = "/sandbox/code.py"
_CONTAINER_INPUT_DIRECTORY: Final = "/sandbox/inputs"
_CONTAINER_OUTPUT_PATH: Final = "/sandbox/output"
_DOCKER_PIDS_LIMIT: Final = 64
_DOCKER_UID: Final = 65_532
_UNSAFE_MOUNT_SOURCE_CHARACTERS: Final = frozenset("\x00\r\n,:=")
_IMAGE_REFERENCE: Final = re.compile(
    r"(?:[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?/)?"
    + r"[a-z0-9]+(?:[._-][a-z0-9]+)*(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*"
    + r"@sha256:[0-9a-f]{64}"
)


@final
@dataclass(frozen=True, slots=True)
class DockerPolicyError(ValueError):
    """A Docker policy value or mount source is unsafe."""

    value: str
    reason: str

    @override
    def __str__(self) -> str:
        return f"unsafe Docker policy value {self.value!r}: {self.reason}"


@final
@dataclass(frozen=True, slots=True)
class DockerExecutionRequest:
    """Validated host paths and immutable limits for one Docker execution policy."""

    image: DockerImageReference
    code_path: Path
    input_paths: tuple[Path, ...]
    output_path: Path
    resource_limits: SandboxResourceLimits
    environment: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ = parse_docker_image_reference(self.image)


@final
@dataclass(frozen=True, slots=True)
class DockerSecurityProfile:
    image_digest: str
    cpu_millis: int
    memory_mb: int
    timeout_seconds: int
    pids_limit: int
    network: str
    root_read_only: bool
    code_read_only: bool
    inputs_read_only: bool
    output_read_write: bool
    input_mount_count: int
    user_id: int
    capabilities_dropped: str
    no_new_privileges: bool
    pull_policy: str
    environment_forwarded: bool


def effective_security_profile(
    request: DockerExecutionRequest,
) -> DockerSecurityProfile:
    return DockerSecurityProfile(
        image_digest=str(request.image).split("@", 1)[1],
        cpu_millis=request.resource_limits.cpu_millis,
        memory_mb=request.resource_limits.memory_mb,
        timeout_seconds=request.resource_limits.timeout_seconds,
        pids_limit=_DOCKER_PIDS_LIMIT,
        network="none",
        root_read_only=True,
        code_read_only=True,
        inputs_read_only=True,
        output_read_write=True,
        input_mount_count=len(request.input_paths),
        user_id=_DOCKER_UID,
        capabilities_dropped="ALL",
        no_new_privileges=True,
        pull_policy="never",
        environment_forwarded=bool(request.environment),
    )


def parse_docker_image_reference(raw_image: str) -> DockerImageReference:
    """Parse an immutable sha256-pinned Docker image reference without a tag."""

    if _IMAGE_REFERENCE.fullmatch(raw_image) is None:
        raise DockerPolicyError(
            raw_image, "must be a sha256 digest-only image reference"
        )
    return DockerImageReference(raw_image)


def docker_container_name(request: DockerExecutionRequest) -> DockerContainerName:
    """Derive a safe deterministic Docker container name from the output directory."""

    suffix = sha256(str(request.output_path).encode("utf-8")).hexdigest()[:16]
    return DockerContainerName(f"vnalpha-sandbox-{suffix}")


def build_docker_run_argv(request: DockerExecutionRequest) -> tuple[str, ...]:
    """Build the fixed, hardened Docker argv for one validated execution request."""

    if request.environment:
        raise DockerPolicyError("environment", "environment forwarding is forbidden")

    code_path = _validate_regular_file(request.code_path, "code path")
    input_paths = tuple(
        _validate_input_path(path, "input path") for path in request.input_paths
    )
    output_path = _validate_directory(request.output_path, "output path")
    _validate_distinct_mount_sources(code_path, input_paths, output_path)

    input_mounts = tuple(
        _read_only_mount(path, f"{_CONTAINER_INPUT_DIRECTORY}/{index}")
        for index, path in enumerate(input_paths)
    )
    return (
        "docker",
        "run",
        f"--name={docker_container_name(request)}",
        "--rm",
        "--pull=never",
        "--network=none",
        "--read-only",
        f"--user={_DOCKER_UID}",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        f"--pids-limit={_DOCKER_PIDS_LIMIT}",
        f"--cpus={_format_cpu_limit(request.resource_limits.cpu_millis)}",
        f"--memory={request.resource_limits.memory_mb}m",
        f"--memory-swap={request.resource_limits.memory_mb}m",
        "--workdir=/sandbox",
        _read_only_mount(code_path, _CONTAINER_CODE_PATH),
        *input_mounts,
        _read_write_mount(output_path, _CONTAINER_OUTPUT_PATH),
        "--entrypoint=/usr/local/bin/python",
        str(request.image),
        _CONTAINER_CODE_PATH,
    )


def _validate_regular_file(path: Path, label: str) -> Path:
    canonical_path = _validate_mount_path(path, label)
    if not stat.S_ISREG(canonical_path.lstat().st_mode):
        raise DockerPolicyError(str(path), f"{label} must be a regular file")
    return canonical_path


def _validate_input_path(path: Path, label: str) -> Path:
    canonical_path = _validate_mount_path(path, label)
    mode = canonical_path.lstat().st_mode
    if not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
        raise DockerPolicyError(
            str(path), f"{label} must be a regular file or directory"
        )
    if stat.S_ISDIR(mode):
        _validate_mount_tree(canonical_path, label)
    return canonical_path


def _validate_directory(path: Path, label: str) -> Path:
    canonical_path = _validate_mount_path(path, label)
    if not stat.S_ISDIR(canonical_path.lstat().st_mode):
        raise DockerPolicyError(str(path), f"{label} must be a directory")
    _validate_mount_tree(canonical_path, label)
    return canonical_path


def _validate_mount_path(path: Path, label: str) -> Path:
    raw_path = str(path)
    has_unsafe_syntax = not path.is_absolute() or any(
        character in _UNSAFE_MOUNT_SOURCE_CHARACTERS for character in raw_path
    )
    if has_unsafe_syntax:
        raise DockerPolicyError(raw_path, f"{label} must be an absolute plain path")
    try:
        canonical_path = path.resolve(strict=True)
    except OSError as exc:
        raise DockerPolicyError(raw_path, f"{label} must resolve on the host") from exc
    if canonical_path != path:
        raise DockerPolicyError(raw_path, f"{label} must not traverse a symlink")
    return canonical_path


def _validate_distinct_mount_sources(
    code_path: Path,
    input_paths: tuple[Path, ...],
    output_path: Path,
) -> None:
    mount_sources = (code_path, *input_paths, output_path)
    for index, source in enumerate(mount_sources):
        for other_source in mount_sources[index + 1 :]:
            if source.is_relative_to(other_source) or other_source.is_relative_to(
                source
            ):
                raise DockerPolicyError("mount sources", "must not overlap")


def _validate_mount_tree(root: Path, label: str) -> None:
    pending_directories = [root]
    while pending_directories:
        directory = pending_directories.pop()
        try:
            entries = tuple(directory.iterdir())
        except OSError as exc:
            raise DockerPolicyError(
                str(directory), f"{label} must be readable"
            ) from exc
        for entry in entries:
            try:
                mode = entry.lstat().st_mode
            except OSError as exc:
                raise DockerPolicyError(
                    str(entry), f"{label} must be inspectable"
                ) from exc
            if stat.S_ISREG(mode):
                continue
            if stat.S_ISDIR(mode):
                pending_directories.append(entry)
                continue
            raise DockerPolicyError(
                str(entry), f"{label} must not contain symbolic or special files"
            )


def _read_only_mount(source: Path, destination: str) -> str:
    return (
        f"--mount=type=bind,src={source},dst={destination},"
        "bind-recursive=disabled,readonly"
    )


def _read_write_mount(source: Path, destination: str) -> str:
    return f"--mount=type=bind,src={source},dst={destination},bind-recursive=disabled"


def _format_cpu_limit(cpu_millis: int) -> str:
    whole_cpus, fractional_millis = divmod(cpu_millis, 1_000)
    return f"{whole_cpus}.{fractional_millis:03d}"
