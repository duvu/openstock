from __future__ import annotations

import importlib.util
from dataclasses import FrozenInstanceError
from pathlib import Path
from socket import AF_UNIX, SOCK_STREAM, socket

import pytest

from vnalpha.sandbox.docker_runner import (
    DockerCommand,
    DockerExecutionRequest,
    DockerExecutionResult,
    DockerImageReference,
    DockerPolicyError,
    DockerPreflightResult,
    build_docker_run_argv,
    docker_container_name,
    parse_docker_image_reference,
)
from vnalpha.sandbox.models import SandboxResourceLimits


def test_docker_runner_module_exists() -> None:
    # Given
    module_name = "vnalpha.sandbox.docker_runner"

    # When
    module_spec = importlib.util.find_spec(module_name)

    # Then
    assert module_spec is not None


def test_build_docker_run_argv_uses_only_hardened_fixed_options(
    tmp_path: Path,
) -> None:
    # Given
    code_path = tmp_path / "job.py"
    _ = code_path.write_text("print('research')\n")
    input_path = tmp_path / "prices.csv"
    _ = input_path.write_text("symbol,close\nFPT,100\n")
    output_path = tmp_path / "output"
    output_path.mkdir()
    image = parse_docker_image_reference(
        f"registry.example/openstock/sandbox@sha256:{'a' * 64}"
    )
    request = DockerExecutionRequest(
        image=image,
        code_path=code_path,
        input_paths=(input_path,),
        output_path=output_path,
        resource_limits=SandboxResourceLimits(
            cpu_millis=250,
            memory_mb=128,
            timeout_seconds=30,
        ),
    )

    # When
    argv = build_docker_run_argv(request)

    # Then
    assert argv == (
        "docker",
        "run",
        f"--name={docker_container_name(request)}",
        "--rm",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--user=65532",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
        "--pids-limit=64",
        "--cpus=0.250",
        "--memory=128m",
        "--memory-swap=128m",
        "--workdir=/sandbox",
        f"--mount=type=bind,src={code_path},dst=/sandbox/code.py,bind-recursive=disabled,readonly",
        f"--mount=type=bind,src={input_path},dst=/sandbox/inputs/0,bind-recursive=disabled,readonly",
        f"--mount=type=bind,src={output_path},dst=/sandbox/output,bind-recursive=disabled",
        "--entrypoint=/usr/local/bin/python",
        str(image),
        "/sandbox/code.py",
    )


@pytest.mark.parametrize(
    "raw_image",
    (
        "registry.example/openstock/sandbox:stable",
        "registry.example/openstock/sandbox@sha256:ABCDEF",
        "registry.example/openstock/sandbox@sha512:" + "a" * 128,
        "registry.example/openstock/sandbox@sha256:" + "a" * 63,
    ),
)
def test_parse_docker_image_reference_rejects_non_digest_images(raw_image: str) -> None:
    # Given
    invalid_image = raw_image

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = parse_docker_image_reference(invalid_image)


def test_docker_execution_request_rejects_a_direct_tag_reference(
    tmp_path: Path,
) -> None:
    # Given
    request = _request(tmp_path)

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = DockerExecutionRequest(
            image=DockerImageReference("registry.example/openstock/sandbox:stable"),
            code_path=request.code_path,
            input_paths=request.input_paths,
            output_path=request.output_path,
            resource_limits=request.resource_limits,
        )


def test_build_docker_run_argv_rejects_delimiter_bearing_mount_path(
    tmp_path: Path,
) -> None:
    # Given
    unsafe_input_path = tmp_path / "prices.csv,readonly"
    _ = unsafe_input_path.write_text("symbol,close\nFPT,100\n")
    request = _request(tmp_path, input_paths=(unsafe_input_path,))

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = build_docker_run_argv(request)


def test_build_docker_run_argv_rejects_symlinked_mount_source(tmp_path: Path) -> None:
    # Given
    target_path = tmp_path / "prices.csv"
    _ = target_path.write_text("symbol,close\nFPT,100\n")
    symlink_path = tmp_path / "prices-link.csv"
    symlink_path.symlink_to(target_path)
    request = _request(tmp_path, input_paths=(symlink_path,))

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = build_docker_run_argv(request)


def test_build_docker_run_argv_rejects_socket_mount_source(tmp_path: Path) -> None:
    # Given
    socket_path = tmp_path / "sandbox.sock"
    with socket(AF_UNIX, SOCK_STREAM) as unix_socket:
        unix_socket.bind(str(socket_path))
        request = _request(tmp_path, input_paths=(socket_path,))

        # When / Then
        with pytest.raises(DockerPolicyError):
            _ = build_docker_run_argv(request)


def test_build_docker_run_argv_rejects_a_socket_inside_an_input_directory(
    tmp_path: Path,
) -> None:
    # Given
    input_directory = tmp_path / "inputs"
    input_directory.mkdir()
    socket_path = input_directory / "sandbox.sock"
    with socket(AF_UNIX, SOCK_STREAM) as unix_socket:
        unix_socket.bind(str(socket_path))
        request = _request(tmp_path, input_paths=(input_directory,))

        # When / Then
        with pytest.raises(DockerPolicyError):
            _ = build_docker_run_argv(request)


def test_build_docker_run_argv_rejects_output_nested_below_an_input_mount(
    tmp_path: Path,
) -> None:
    # Given
    input_directory = tmp_path / "inputs"
    input_directory.mkdir()
    nested_output_path = input_directory / "output"
    nested_output_path.mkdir()
    base_request = _request(tmp_path, input_paths=(input_directory,))
    request = DockerExecutionRequest(
        image=base_request.image,
        code_path=base_request.code_path,
        input_paths=base_request.input_paths,
        output_path=nested_output_path,
        resource_limits=base_request.resource_limits,
    )

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = build_docker_run_argv(request)


def test_build_docker_run_argv_rejects_environment_forwarding(tmp_path: Path) -> None:
    # Given
    request = _request(tmp_path, environment=("TOKEN=secret",))

    # When / Then
    with pytest.raises(DockerPolicyError):
        _ = build_docker_run_argv(request)


def test_docker_command_protocol_accepts_a_fake_boundary() -> None:
    # Given
    class FakeDockerCommand:
        def invoke(
            self, argv: tuple[str, ...], *, timeout_seconds: int
        ) -> DockerExecutionResult:
            del argv, timeout_seconds
            return DockerExecutionResult(return_code=0, stdout=b"", stderr=b"")

    command: DockerCommand = FakeDockerCommand()
    preflight = DockerPreflightResult(
        docker_available=True,
        linux_supported=True,
        detail="not executed in Task 2",
    )

    # When
    result = command.invoke(("docker", "version"), timeout_seconds=5)

    # Then
    assert preflight.docker_available
    assert result.return_code == 0


def test_docker_preflight_result_is_immutable() -> None:
    # Given
    preflight = DockerPreflightResult(
        docker_available=True,
        linux_supported=True,
        detail="not executed in Task 2",
    )
    attribute_name = "docker_available"

    # When / Then
    with pytest.raises(FrozenInstanceError):
        setattr(preflight, attribute_name, False)


def test_docker_execution_result_is_immutable() -> None:
    # Given
    result = DockerExecutionResult(return_code=0, stdout=b"", stderr=b"")
    attribute_name = "return_code"

    # When / Then
    with pytest.raises(FrozenInstanceError):
        setattr(result, attribute_name, 1)


def _request(
    tmp_path: Path,
    *,
    input_paths: tuple[Path, ...] = (),
    environment: tuple[str, ...] = (),
) -> DockerExecutionRequest:
    code_path = tmp_path / "job.py"
    _ = code_path.write_text("print('research')\n")
    output_path = tmp_path / "output"
    output_path.mkdir()
    return DockerExecutionRequest(
        image=parse_docker_image_reference(
            f"registry.example/openstock/sandbox@sha256:{'a' * 64}"
        ),
        code_path=code_path,
        input_paths=input_paths,
        output_path=output_path,
        resource_limits=SandboxResourceLimits(
            cpu_millis=250,
            memory_mb=128,
            timeout_seconds=30,
        ),
        environment=environment,
    )
