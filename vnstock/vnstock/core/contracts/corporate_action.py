"""Canonical provider contract for corporate-action evidence."""

from vnstock.core.contracts.base import DatasetContract

CORPORATE_ACTIONS_CONTRACT = DatasetContract(
    dataset="reference.corporate_actions",
    required_columns=[
        "provider_event_id",
        "symbol",
        "action_type",
        "provider",
        "source_reference",
        "source_version",
        "content_hash",
        "source_payload_json",
    ],
    optional_columns=[
        "announced_at",
        "ex_date",
        "record_date",
        "effective_date",
        "cash_amount",
        "ratio",
        "ratio_text",
        "subscription_price",
        "reference_price",
        "currency",
        "title",
        "quality_status",
    ],
    dtype_rules={
        "provider_event_id": "string",
        "symbol": "string",
        "action_type": "string",
        "provider": "string",
        "source_reference": "string",
        "source_version": "string",
        "content_hash": "string",
        "source_payload_json": "string",
    },
    time_column="effective_date",
    symbol_column="symbol",
    validator=None,
    description=(
        "Provider-normalized corporate-action evidence. Source records remain "
        "untrusted until vnalpha canonical reconciliation succeeds."
    ),
)
