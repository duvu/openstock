"""Publication-aware fundamentals vertical (issue #257).

A small, provider-independent fundamentals path for current-symbol research
using only facts available by a requested as-of date. Warehouse facts are
authoritative; derived ratios reproduce deterministically from canonical facts.
"""

from vnalpha.fundamentals.models import (
    FISCAL_PERIODS,
    STATEMENT_SCOPES,
    AuditStatus,
    FundamentalFact,
    StatementScope,
    compute_debt_to_equity,
    compute_roe,
    fact_content_hash,
)
from vnalpha.fundamentals.repository import (
    as_of_snapshot,
    get_fact_revisions,
    upsert_fundamental_fact,
)

__all__ = [
    "FISCAL_PERIODS",
    "STATEMENT_SCOPES",
    "AuditStatus",
    "FundamentalFact",
    "StatementScope",
    "as_of_snapshot",
    "compute_debt_to_equity",
    "compute_roe",
    "fact_content_hash",
    "get_fact_revisions",
    "upsert_fundamental_fact",
]
