from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _module():
    script_path = Path(__file__).parents[1] / "postgresql_storage_inventory.py"
    spec = importlib.util.spec_from_file_location(
        "postgresql_storage_inventory", script_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_storage_inventory_classifies_current_database_coupling(tmp_path: Path) -> None:
    files = {
        "vnalpha/src/vnalpha/warehouse/connection.py": (
            "import duckdb\n"
            "conn: duckdb.DuckDBPyConnection\n"
            'conn.execute("CREATE TABLE evidence(id INTEGER)")\n'
        ),
        "vnalpha/src/vnalpha/provisioning_queue/repository.py": (
            "import sqlite3\n"
            'conn = sqlite3.connect("queue.db")\n'
            'conn.execute("PRAGMA journal_mode=WAL")\n'
        ),
        "vnalpha/tests/test_storage.py": 'database = ":memory:"\n',
        "packaging/openstock.service": (
            "ExecStart=/usr/bin/flock "
            "/var/lib/openstock/warehouse/warehouse.duckdb\n"
        ),
    }
    for relative_path, content in files.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    (tmp_path / ".env").write_text(
        "VNALPHA_WAREHOUSE_PATH=warehouse.duckdb password=must-not-read\n",
        encoding="utf-8",
    )

    module = _module()
    report = module.scan_repository(tmp_path)

    assert module.validate_report(report) == ()
    findings = report["findings"]
    assert any(
        finding["domain"] == "schema"
        and finding["classification"] == "schema redesign"
        and finding["owner_issue"] == 393
        for finding in findings
    )
    assert any(
        finding["domain"] == "queue"
        and finding["classification"] == "behavior/invariant redesign"
        and finding["owner_issue"] == 395
        for finding in findings
    )
    assert any(
        finding["kind"] == "file_lock" and finding["owner_issue"] == 399
        for finding in findings
    )
    assert report["summary"]["files_with_findings"] == 4
    assert report["scan_policy"]["source"] == "git tracked files"
    assert "must-not-read" not in str(report)
