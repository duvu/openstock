"""Log bundle creator — packages run logs into a portable tar.gz artifact."""

from __future__ import annotations

import json
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# Files excluded from bundle by default (may contain secrets or be too large)
_EXCLUDED_PATTERNS: tuple[str, ...] = (
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.env",
    ".env*",
    "*.credentials",
    "secrets*",
)

# Files always included
_INCLUDED_FILES = {
    "audit.jsonl",
    "app.jsonl",
    "errors.jsonl",
    "trace.jsonl",
    "commands.jsonl",
    "ai-agent-summary.md",
    "environment.json",
    "README.md",
}


def _is_safe(path: Path) -> bool:
    name = path.name
    for pat in _EXCLUDED_PATTERNS:
        if pat.startswith("*"):
            if name.endswith(pat[1:]):
                return False
        elif pat.endswith("*"):
            if name.startswith(pat[:-1]):
                return False
        else:
            if name == pat:
                return False
    return True


def create_bundle(
    run_dir: Path,
    output_path: Path | None = None,
    *,
    include_schemas: bool = True,
) -> Path:
    """Create a tar.gz bundle of the run_dir.

    Returns the path of the created bundle.

    Args:
        run_dir: Path to the run directory to bundle.
        output_path: Where to write the .tar.gz (defaults to run_dir.parent).
        include_schemas: Whether to include JSON schema files from logs/schemas/.
    """
    if output_path is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        bundle_name = f"vnalpha-logs-{run_dir.name}-{ts}.tar.gz"
        output_path = run_dir.parent.parent / bundle_name

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tarfile.open(output_path, "w:gz") as tar:
        # Add run-dir files
        for fname in _INCLUDED_FILES:
            fpath = run_dir / fname
            if fpath.exists() and _is_safe(fpath):
                tar.add(fpath, arcname=f"run/{fname}")

        # Add any extra safe files in run_dir not in the standard set
        for fpath in sorted(run_dir.iterdir()):
            if (
                fpath.name not in _INCLUDED_FILES
                and _is_safe(fpath)
                and fpath.is_file()
            ):
                tar.add(fpath, arcname=f"run/{fpath.name}")

        # Add schemas if available
        if include_schemas:
            schemas_dir = run_dir.parent.parent / "schemas"
            if schemas_dir.exists():
                for schema_file in sorted(schemas_dir.glob("*.json")):
                    if _is_safe(schema_file):
                        tar.add(schema_file, arcname=f"schemas/{schema_file.name}")

        # Write a bundle manifest
        manifest = {
            "run_id": run_dir.name,
            "bundled_at": datetime.now(timezone.utc).isoformat(),
            "source_dir": str(run_dir),
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(manifest, tmp, indent=2)
            tmp_path = Path(tmp.name)
        try:
            tar.add(tmp_path, arcname="bundle-manifest.json")
        finally:
            tmp_path.unlink(missing_ok=True)

    return output_path
