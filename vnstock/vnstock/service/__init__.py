"""vnstock local data service.

Exposes data-read HTTP endpoints on localhost (default: 127.0.0.1:6900).

Start the service::

    vnstock serve --host 127.0.0.1 --port 6900

Or via Python::

    from vnstock.service import run_server
    run_server(host="127.0.0.1", port=6900)

Security guarantees:
- No login endpoint (auth is CLI-only).
- No account, order, portfolio, transfer, or margin endpoints.
- Default binding is localhost-only.
- Token material is never returned in any response.
"""

from __future__ import annotations

from vnstock.service.server import run_server

__all__ = ["run_server"]
