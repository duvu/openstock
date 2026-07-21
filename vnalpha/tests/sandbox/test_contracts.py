from __future__ import annotations


def test_filesystem_policy_canonicalizes_approved_relative_read_paths() -> None:
    from vnalpha.sandbox.contracts import SandboxFilesystemPolicy

    policy = SandboxFilesystemPolicy.model_validate(
        {"approved_read_paths": ("inputs/candidate.json", "data/prices.parquet")}
    )

    assert policy.approved_read_paths == (
        "inputs/candidate.json",
        "data/prices.parquet",
    )
    assert policy.writable_directory == "output"
