from __future__ import annotations

import importlib.util
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


def _load_script():
    repo_root = Path(__file__).resolve().parents[4]
    script_path = repo_root / "scripts" / "audit-vnstock-service.py"
    spec = importlib.util.spec_from_file_location("vnstock_service_audit", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_service_audit_discovers_and_probes_advertised_provider_contract(
    tmp_path,
) -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, _format, *_args):
            return

        def do_GET(self):
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            payload = {}
            status = 200
            if parsed.path == "/healthz":
                payload = {"status": "ok", "service": "vnstock"}
            elif parsed.path == "/v1/providers":
                payload = {"providers": ["KBS"]}
            elif parsed.path == "/v1/providers/capabilities":
                payload = {
                    "capabilities": {
                        "KBS": {
                            "equity.ohlcv": {
                                "supported": True,
                                "status": "stable",
                                "auth_required": False,
                            }
                        }
                    }
                }
            elif parsed.path == "/v1/providers/health":
                payload = {"health": {}, "providers": []}
            elif parsed.path == "/v1/auth/status":
                payload = {"auth_status": {}}
            elif parsed.path == "/v1/auth/providers":
                payload = {"auth_providers": {"KBS": {"required": False}}}
            elif parsed.path == "/v1/equity/ohlcv":
                assert query["source"] == ["KBS"]
                assert query["symbol"] == ["FPT"]
                payload = {
                    "data": [
                        {
                            "symbol": "FPT",
                            "time": "2026-07-21T00:00:00+00:00",
                            "close": 100.0,
                        }
                    ],
                    "meta": {
                        "dataset": "equity.ohlcv",
                        "provider": "KBS",
                        "quality_status": "PASS",
                        "runtime_path": "plugin_runtime",
                    },
                    "diagnostics": {},
                }
            else:
                status = 404
                payload = {"error": "not_found", "message": parsed.path}
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        module = _load_script()
        output_dir = tmp_path / "audit"
        exit_code = module.main(
            [
                "--base-url",
                f"http://127.0.0.1:{server.server_port}",
                "--providers",
                "KBS",
                "--datasets",
                "equity.ohlcv",
                "--start",
                "2026-07-01",
                "--end",
                "2026-07-21",
                "--delay",
                "0",
                "--output-dir",
                str(output_dir),
            ]
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert exit_code == 0
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert report["summary"] == {"PASS": 1}
    result = report["results"][0]
    assert result["provider"] == "KBS"
    assert result["dataset"] == "equity.ohlcv"
    assert result["actual_provider"] == "KBS"
    assert result["row_count"] == 1
    assert result["runtime_path"] == "plugin_runtime"
    assert result["sample_rows"][0]["symbol"] == "FPT"
    assert (output_dir / "matrix.csv").is_file()
    assert (output_dir / "report.md").is_file()
