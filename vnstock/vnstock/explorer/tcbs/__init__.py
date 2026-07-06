"""TCBS data explorer module.

SCOPE / SAFETY GATE
-------------------
This module exposes **read-only market-data** endpoints from TCBS APIs.
It does NOT implement any broker, account, order, portfolio, iCopy, margin,
or transfer operations.  Those APIs require authentication and fall outside
the scope of vnstock.

Authentication
--------------
TCBS market-data APIs require a Bearer token as of 2025.  Use the CLI to
obtain and cache a token::

    vnstock-tcbs-login

Or acquire a token programmatically::

    from vnstock.explorer.tcbs import TCBSAuth
    auth = TCBSAuth()
    # token = auth.login(username="105C...", password="...")
    # If OTP required: token = auth.confirm_otp(otp_session, "123456")

Vendor-derived fields (ratings, signals, analyst recommendations) are surfaced
as-is from the upstream response under explicit ``vendor_*`` or ``signal_*``
column names.  They are NOT investment advice.  Callers should treat them as
raw data from the data provider.

TCBS is NOT the default provider for any vnstock UI method.  Pass
``source='tcbs'`` explicitly to route calls here.

API contract may drift without notice.
"""

from vnstock.explorer.tcbs.auth import (  # noqa: F401
    TCBSAuth,
    TCBSAuthError,
    TCBSOTPRequired,
)
from vnstock.explorer.tcbs.company import Company  # noqa: F401
from vnstock.explorer.tcbs.financial import Finance  # noqa: F401
from vnstock.explorer.tcbs.listing import Listing  # noqa: F401
from vnstock.explorer.tcbs.quote import Quote  # noqa: F401
from vnstock.explorer.tcbs.screener import Screener  # noqa: F401
from vnstock.explorer.tcbs.trading import Trading  # noqa: F401

__all__ = [
    "TCBSAuth",
    "TCBSAuthError",
    "TCBSOTPRequired",
    "Quote",
    "Trading",
    "Company",
    "Finance",
    "Listing",
    "Screener",
]
