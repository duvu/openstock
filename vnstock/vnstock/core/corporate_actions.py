"""Provider-independent normalization for corporate-action evidence."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from enum import StrEnum
from typing import Any, Mapping

import pandas as pd

CORPORATE_ACTION_CONTRACT_VERSION = "corporate-actions-v1"
CORPORATE_ACTION_COLUMNS = [
    "provider_event_id",
    "symbol",
    "action_type",
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
    "provider",
    "source_reference",
    "source_version",
    "content_hash",
    "source_payload_json",
    "quality_status",
]


class CorporateActionType(StrEnum):
    CASH_DIVIDEND = "CASH_DIVIDEND"
    STOCK_DIVIDEND = "STOCK_DIVIDEND"
    STOCK_BONUS = "STOCK_BONUS"
    SPLIT = "SPLIT"
    CONSOLIDATION = "CONSOLIDATION"
    RIGHTS_ISSUE = "RIGHTS_ISSUE"
    REFERENCE_PRICE_ADJUSTMENT = "REFERENCE_PRICE_ADJUSTMENT"
    ADDITIONAL_LISTING = "ADDITIONAL_LISTING"
    SYMBOL_CHANGE = "SYMBOL_CHANGE"
    DELISTING = "DELISTING"
    OTHER = "OTHER"


def empty_corporate_actions(provider: str) -> pd.DataFrame:
    frame = pd.DataFrame(columns=CORPORATE_ACTION_COLUMNS)
    frame.attrs.update(
        {
            "provider": provider.upper(),
            "dataset": "reference.corporate_actions",
            "contract_version": CORPORATE_ACTION_CONTRACT_VERSION,
            "result_semantics": "valid_empty",
        }
    )
    return frame


def normalize_corporate_actions(
    raw: pd.DataFrame | list[Mapping[str, Any]] | None,
    *,
    provider: str,
    symbol: str,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    provider = provider.upper().strip()
    symbol = symbol.upper().strip()
    if raw is None:
        return empty_corporate_actions(provider)
    frame = raw.copy() if isinstance(raw, pd.DataFrame) else pd.DataFrame(raw)
    if frame.empty:
        return empty_corporate_actions(provider)
    frame.columns = [_snake_case(str(column)) for column in frame.columns]
    records = [
        _normalize_record(record, provider=provider, default_symbol=symbol)
        for record in frame.to_dict(orient="records")
    ]
    result = pd.DataFrame(records, columns=CORPORATE_ACTION_COLUMNS)
    for column in ("announced_at", "ex_date", "record_date", "effective_date"):
        result[column] = pd.to_datetime(result[column], errors="coerce").dt.date
    lower = _parse_date(start)
    upper = _parse_date(end)
    if lower is not None or upper is not None:
        anchor = (
            result["effective_date"]
            .combine_first(result["ex_date"])
            .combine_first(result["record_date"])
            .combine_first(result["announced_at"])
        )
        if lower is not None:
            result = result[anchor >= pd.Timestamp(lower)]
        if upper is not None:
            result = result[anchor <= pd.Timestamp(upper)]
    result = result.sort_values(
        ["effective_date", "announced_at", "provider_event_id"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)
    result = result.astype(object).where(pd.notna(result), None)
    result.attrs.update(
        {
            "provider": provider,
            "dataset": "reference.corporate_actions",
            "contract_version": CORPORATE_ACTION_CONTRACT_VERSION,
            "result_semantics": "valid_empty" if result.empty else "complete_response",
            "source_authority": "MARKET_DATA_PROVIDER",
        }
    )
    return result


def _normalize_record(
    record: Mapping[str, Any], *, provider: str, default_symbol: str
) -> dict[str, Any]:
    raw = {str(key).strip().lower(): _json_safe(value) for key, value in record.items()}
    symbol = str(
        _first(raw, "ticker", "symbol", default=default_symbol) or default_symbol
    ).upper()
    provider_event_id = str(
        _first(raw, "id", "event_id", "eventid", "news_id", default="") or ""
    ).strip()
    if not provider_event_id:
        provider_event_id = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()[:24]
    title = str(
        _first(
            raw,
            "event_title_en",
            "event_title_vi",
            "title",
            "event_name_en",
            "event_name_vi",
            default="",
        )
        or ""
    ).strip()
    event_code = str(
        _first(raw, "event_code", "eventcode", "category", default="") or ""
    ).upper()
    action_type = _classify(event_code=event_code, title=title, record=raw)
    announced_at = _date_value(
        raw, "public_date", "published_at", "display_date1", "create_date"
    )
    ex_date = _date_value(raw, "exright_date", "ex_date", "exdate")
    record_date = _date_value(raw, "record_date", "recorddate")
    effective_date = _date_value(
        raw,
        "effective_date",
        "payout_date",
        "listing_date",
        "issue_date",
        "display_date2",
    )
    cash_amount = _float_value(raw, "value_per_share", "cash_amount", "dividend_value")
    ratio = _ratio_value(raw, "exercise_ratio", "ratio", "stock_ratio")
    ratio_text = (
        str(
            _first(raw, "ratio_text", "action_type_en", "action_type_vi", default="")
            or ""
        ).strip()
        or None
    )
    subscription_price = _float_value(raw, "subscription_price", "issue_price", "price")
    reference_price = _float_value(raw, "reference_price", "ref_price")
    payload_json = json.dumps(
        raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    content_hash = hashlib.sha256(payload_json.encode("utf-8")).hexdigest()
    return {
        "provider_event_id": provider_event_id,
        "symbol": symbol,
        "action_type": action_type.value,
        "announced_at": announced_at,
        "ex_date": ex_date,
        "record_date": record_date,
        "effective_date": effective_date,
        "cash_amount": cash_amount,
        "ratio": ratio,
        "ratio_text": ratio_text,
        "subscription_price": subscription_price,
        "reference_price": reference_price,
        "currency": "VND"
        if cash_amount is not None or subscription_price is not None
        else None,
        "title": title or None,
        "provider": provider,
        "source_reference": f"{provider.lower()}://company/{symbol}/events/{provider_event_id}",
        "source_version": CORPORATE_ACTION_CONTRACT_VERSION,
        "content_hash": content_hash,
        "source_payload_json": payload_json,
        "quality_status": "UNCLASSIFIED"
        if action_type is CorporateActionType.OTHER
        else "NORMALIZED",
    }


def _classify(
    *, event_code: str, title: str, record: Mapping[str, Any]
) -> CorporateActionType:
    text = " ".join(
        str(value or "")
        for value in (
            event_code,
            title,
            record.get("event_name_en"),
            record.get("event_name_vi"),
            record.get("action_type_en"),
            record.get("action_type_vi"),
        )
    ).lower()
    if any(token in text for token in ("delist", "hủy niêm yết", "huy niem yet")):
        return CorporateActionType.DELISTING
    if any(token in text for token in ("symbol change", "đổi mã", "doi ma")):
        return CorporateActionType.SYMBOL_CHANGE
    if any(
        token in text
        for token in ("consolidation", "reverse split", "gộp cổ phiếu", "gop co phieu")
    ):
        return CorporateActionType.CONSOLIDATION
    if any(
        token in text
        for token in ("stock split", "split", "tách cổ phiếu", "tach co phieu")
    ):
        return CorporateActionType.SPLIT
    if any(
        token in text
        for token in ("rights issue", "right issue", "quyền mua", "quyen mua")
    ):
        return CorporateActionType.RIGHTS_ISSUE
    if any(
        token in text for token in ("bonus issue", "cổ phiếu thưởng", "co phieu thuong")
    ):
        return CorporateActionType.STOCK_BONUS
    if any(
        token in text
        for token in ("stock dividend", "cổ tức bằng cổ phiếu", "co tuc bang co phieu")
    ):
        return CorporateActionType.STOCK_DIVIDEND
    if (
        event_code == "DIV"
        or "dividend" in text
        or "cổ tức" in text
        or "co tuc" in text
    ):
        if _float_value(
            record, "value_per_share", "cash_amount", "dividend_value"
        ) is not None or any(
            token in text for token in ("cash", "tiền mặt", "tien mat")
        ):
            return CorporateActionType.CASH_DIVIDEND
        if _ratio_value(record, "exercise_ratio", "ratio", "stock_ratio") is not None:
            return CorporateActionType.STOCK_DIVIDEND
    if any(
        token in text
        for token in ("reference price", "giá tham chiếu", "gia tham chieu")
    ):
        return CorporateActionType.REFERENCE_PRICE_ADJUSTMENT
    if event_code == "ISS" or any(
        token in text
        for token in ("share issue", "phát hành", "phat hanh", "additional listing")
    ):
        return CorporateActionType.ADDITIONAL_LISTING
    return CorporateActionType.OTHER


def _snake_case(value: str) -> str:
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value.strip())
    return re.sub(r"[^a-zA-Z0-9]+", "_", cleaned).strip("_").lower()


def _first(record: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and not (isinstance(value, float) and pd.isna(value)):
            return value
    return default


def _parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _date_value(record: Mapping[str, Any], *keys: str) -> date | None:
    return _parse_date(_first(record, *keys))


def _float_value(record: Mapping[str, Any], *keys: str) -> float | None:
    value = _first(record, *keys)
    if value is None or value == "":
        return None
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None
    return None if pd.isna(result) else result


def _ratio_value(record: Mapping[str, Any], *keys: str) -> float | None:
    value = _first(record, *keys)
    if value is None or value == "":
        return None
    if isinstance(value, str):
        match = re.search(r"(-?\d+(?:[.,]\d+)?)\s*%", value)
        if match:
            return float(match.group(1).replace(",", ".")) / 100.0
        ratio_match = re.search(r"(\d+(?:[.,]\d+)?)\s*[:/]\s*(\d+(?:[.,]\d+)?)", value)
        if ratio_match:
            left = float(ratio_match.group(1).replace(",", "."))
            right = float(ratio_match.group(2).replace(",", "."))
            return right / left if left else None
    return _float_value(record, *keys)


def _json_safe(value: Any) -> Any:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            pass
    return value
