from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _module():
    script_path = Path(__file__).parents[1] / "openstock-log-triage.py"
    spec = importlib.util.spec_from_file_location("openstock_log_triage", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_triage_normalizes_redacts_and_deduplicates_log_findings(
    tmp_path: Path, capsys
) -> None:
    source = tmp_path / "service.log"
    source.write_text(
        "2026/07/24 08:00:01 provider failed: "
        "https://operator:supersecret@example.test?token=abc123\n"
        "2026/07/24 08:00:02 provider failed: "
        "https://operator:supersecret@example.test?token=abc123\n"
        "Ruff F821 Undefined name `runtime_identity`\n"
        "repository consistency check failed:\n"
        "- vnalpha test suite manifest: test is unclassified: "
        "tests/test_example.py::test_contract\n",
        encoding="utf-8",
    )

    module = _module()
    exit_code = module.main(["--path", str(source), "--json", "--fail-on-findings"])

    report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert "supersecret" not in json.dumps(report)
    assert "abc123" not in json.dumps(report)
    auth = next(
        finding
        for finding in report["findings"]
        if finding["category"] == "AUTHENTICATION"
    )
    assert auth["occurrences"] == 2
    ci_static = next(
        finding
        for finding in report["findings"]
        if "runtime_identity" in finding["evidence"]
    )
    assert (
        ci_static["next_step"]
        == "Run make lint-vnalpha to reproduce the repository static check."
    )
    manifest = next(
        finding
        for finding in report["findings"]
        if "test is unclassified" in finding["evidence"]
    )
    assert manifest["category"] == "CI_STATIC"
    sanitized = module.sanitize(
        "access_token=abc123 client_secret=topsecret "
        "Authorization: Bearer bearer-secret Authorization: Basic basic-secret"
    )
    assert "abc123" not in sanitized
    assert "topsecret" not in sanitized
    assert "bearer-secret" not in sanitized
    assert "basic-secret" not in sanitized
