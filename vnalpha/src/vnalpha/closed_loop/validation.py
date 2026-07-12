from __future__ import annotations

import re
from pathlib import Path

from vnalpha.closed_loop.artifact_integrity import (
    artifact_digest,
    resolve_artifact_root,
    resolve_requested_root,
)
from vnalpha.closed_loop.artifact_integrity import (
    read_json as _read_json,
)
from vnalpha.closed_loop.artifact_integrity import (
    read_text as _read_text,
)
from vnalpha.closed_loop.errors import ClosedLoopBoundaryError
from vnalpha.closed_loop.models import (
    JsonObject,
    LifecycleRecord,
    LifecycleState,
    ValidationCheck,
    ValidationReport,
    now_iso,
)
from vnalpha.closed_loop.paths import validate_identifier
from vnalpha.closed_loop.policy import parse_artifact_type, prohibited_behaviors
from vnalpha.closed_loop.store import ClosedLoopStore
from vnalpha.sandbox.static_guard import SandboxStaticGuard

__all__ = ["resolve_artifact_root", "validate_research_artifact"]


def validate_research_artifact(
    store: ClosedLoopStore,
    artifact_id: str,
    artifact_root: Path | None = None,
    correlation_id: str | None = None,
) -> ValidationReport:
    artifact_id = validate_identifier(artifact_id, "artifact_id")
    root = resolve_requested_root(store, artifact_id, artifact_root)
    scope_safe = root is not None
    digest = ""
    if root is not None:
        try:
            digest = artifact_digest(root)
        except (ClosedLoopBoundaryError, OSError, UnicodeDecodeError):
            scope_safe = False
    manifest = _read_json(root / "manifest.json" if scope_safe and root else None)
    validation = _read_json(root / "validation.json" if scope_safe and root else None)
    result = _read_json(root / "result.json" if scope_safe and root else None)
    summary = _read_text(root / "summary.md" if scope_safe and root else None)
    lineage = _read_json(root / "lineage.json" if scope_safe and root else None)
    generated_code = _read_text(
        root / "generated_code.py" if scope_safe and root else None
    )
    checks = (
        _static_guard_check(root, generated_code, scope_safe),
        _sandbox_execution_check(root, validation, scope_safe),
        ValidationCheck(
            name="output_schema",
            passed=bool(result) and bool(summary.strip()),
            detail="result.json and summary.md are present and non-empty"
            if bool(result) and bool(summary.strip())
            else "result.json or summary.md is missing or invalid",
        ),
        _manifest_check(manifest, artifact_id),
        ValidationCheck(
            name="lineage",
            passed=bool(lineage),
            detail="lineage evidence is present"
            if lineage
            else "lineage.json is missing",
        ),
        _quality_check(root, validation),
        _caveat_check(summary, validation),
        ValidationCheck(
            name="read_only_boundary",
            passed=not prohibited_behaviors(generated_code),
            detail="research code stays inside the read-only boundary"
            if not prohibited_behaviors(generated_code)
            else "generated code contains execution-like behavior",
        ),
    )
    passed = all(check.passed for check in checks)
    resolved_correlation_id = (
        validate_identifier(correlation_id, "correlation_id")
        if correlation_id is not None
        else _correlation_id(validation, artifact_id)
    )
    report = ValidationReport(
        artifact_id=artifact_id,
        correlation_id=resolved_correlation_id,
        checks=checks,
        passed=passed,
        created_at=now_iso(),
        artifact_digest=digest,
        artifact_root=str(root) if scope_safe and root else None,
    )
    store.save_validation_report(report, root if scope_safe else None)
    store.emit(
        "VALIDATION_STARTED",
        correlation_id=report.correlation_id,
        artifact_id=artifact_id,
        status="STARTED",
        detail="research artifact validation started",
    )
    store.emit(
        "VALIDATION_SUCCEEDED" if passed else "VALIDATION_FAILED",
        correlation_id=report.correlation_id,
        artifact_id=artifact_id,
        status="PASSED" if passed else "FAILED",
        detail="research artifact validation completed",
        metadata={
            "failed_checks": [check.name for check in checks if not check.passed]
        },
    )
    store.record_lifecycle(
        LifecycleRecord(
            repair_id=f"artifact:{artifact_id}",
            state=LifecycleState.PROMOTE_READY if passed else LifecycleState.REJECTED,
            correlation_id=report.correlation_id,
            artifact_id=artifact_id,
            created_at=report.created_at,
            detail="validation gate passed" if passed else "validation gate failed",
        )
    )
    return report


def _static_guard_check(
    root: Path | None, code: str, scope_safe: bool
) -> ValidationCheck:
    if not scope_safe or root is None or not (root / "generated_code.py").is_file():
        return ValidationCheck(
            name="static_guard",
            passed=False,
            detail="confined generated_code.py evidence is missing",
        )
    if not code:
        return ValidationCheck(
            name="static_guard", passed=False, detail="generated code is empty"
        )
    evidence = SandboxStaticGuard.evaluate(code)
    return ValidationCheck(
        name="static_guard",
        passed=evidence.allowed,
        detail="sandbox static guard passed"
        if evidence.allowed
        else "sandbox static guard rejected generated code",
    )


def _sandbox_execution_check(
    root: Path | None, validation: JsonObject, scope_safe: bool
) -> ValidationCheck:
    execution = _read_json(root / "execution.json" if scope_safe and root else None)
    status = str(execution.get("status", "")).lower()
    passed = status in {"passed", "succeeded", "success"}
    return ValidationCheck(
        name="sandbox_execution",
        passed=passed,
        detail="sandbox execution evidence passed"
        if passed
        else "sandbox execution evidence is missing or failed",
    )


def _manifest_check(manifest: JsonObject, artifact_id: str) -> ValidationCheck:
    matches = manifest.get("artifact_id") == artifact_id
    artifact_type = manifest.get("artifact_type")
    try:
        parse_artifact_type(artifact_type)
        recognized_type = True
    except (TypeError, ValueError):
        recognized_type = False
    passed = bool(manifest) and matches and recognized_type
    return ValidationCheck(
        name="artifact_manifest",
        passed=passed,
        detail="artifact manifest is present"
        if passed
        else "manifest.json is missing or incomplete",
    )


def _quality_check(root: Path | None, validation: JsonObject) -> ValidationCheck:
    quality = validation.get("quality_status")
    quality_file = _read_json(root / "quality_status.json" if root else None)
    payload = quality if isinstance(quality, dict) and quality else quality_file
    status = str(payload.get("status", "")).lower() if isinstance(payload, dict) else ""
    passed = (
        bool(payload)
        and bool(status)
        and status not in {"fail", "failed", "error", "rejected"}
    )
    return ValidationCheck(
        name="quality_status",
        passed=passed,
        detail="quality status is present" if passed else "quality status is missing",
    )


def _caveat_check(summary: str, validation: JsonObject) -> ValidationCheck:
    caveats = validation.get("caveats")
    passed = isinstance(caveats, list) and bool(caveats)
    passed = passed or re.search(r"\bcaveat(s)?\b", summary, re.IGNORECASE) is not None
    return ValidationCheck(
        name="caveats",
        passed=passed,
        detail="caveats are present" if passed else "caveats are missing",
    )


def _correlation_id(validation: JsonObject, artifact_id: str) -> str:
    value = validation.get("correlation_id")
    if isinstance(value, str) and value:
        try:
            return validate_identifier(value, "correlation_id")
        except ClosedLoopBoundaryError:
            pass
    return f"artifact-{artifact_id}"
