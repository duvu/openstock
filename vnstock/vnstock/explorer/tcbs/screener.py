"""Screener module for TCBS data source (experimental).

SCOPE / SAFETY GATE
-------------------
Read-only screener data (market scan results).
No broker, account, order, iCopy, margin, or transfer endpoints.
TCBS is NOT the default provider — pass source='tcbs' explicitly.

EXPERIMENTAL: This module uses an unofficial endpoint that may drift.
Vendor-derived signal fields (signal, recommendation, rating) are raw data
from TCBS, NOT investment advice.
"""

import json as _json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
from vnai import optimize_execution

from vnstock.core.registry import ProviderRegistry  # noqa: F401
from vnstock.core.utils.client import ProxyConfig, send_request
from vnstock.core.utils.logger import get_logger
from vnstock.core.utils.user_agent import get_headers
from vnstock.explorer.tcbs.auth import TCBSAuth
from vnstock.explorer.tcbs.const import _SCREENER_URL

logger = get_logger(__name__)

# Standard output columns for screener (minimum contract)
_SCREENER_STANDARD_COLUMNS = [
    "symbol",
    "exchange",
    "industry",
]

# Default screener payload (empty = return all symbols with default sort)
_DEFAULT_SCREENER_PAYLOAD: Dict[str, Any] = {
    "page": 0,
    "size": 100,
    "type": "STOCK",
    "filter": [],
}


class Screener:
    """
    Lớp truy cập dữ liệu lọc cổ phiếu từ TCBS (thực nghiệm).

    Endpoint: POST /ligo/v1/watchlist/preview

    EXPERIMENTAL: Endpoint không chính thức, cấu trúc có thể thay đổi.
    Vendor-derived signal fields là dữ liệu thô, không phải lời khuyên đầu tư.

    TCBS là nguồn dữ liệu không chính thức — không đặt làm mặc định.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        random_agent: Optional[bool] = False,
        show_log: Optional[bool] = False,
        proxy_config: Optional[ProxyConfig] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """
        Khởi tạo Screener client cho TCBS.

        Args:
            token: Bearer token TCBS. Nếu None, tự động tải từ
                   TCBS_BEARER_TOKEN env var hoặc ~/.config/vnstock/tcbs_token.json.
            random_agent: Sử dụng user agent ngẫu nhiên. Mặc định False.
            show_log: Hiển thị log debug. Mặc định False.
            proxy_config: Cấu hình proxy. Mặc định None.
            proxy_mode: Chế độ proxy. Mặc định None.
            proxy_list: Danh sách proxy URLs. Mặc định None.
        """
        self.data_source = "TCBS"
        _token = token or TCBSAuth.load_token()
        self.headers = get_headers(
            data_source=self.data_source, random_agent=random_agent
        )
        if _token:
            self.headers["Authorization"] = f"Bearer {_token}"
        else:
            logger.warning(
                "Không tìm thấy TCBS token. Chạy `vnstock-tcbs-login` để đăng nhập."
            )
        self.show_log = show_log

        if proxy_config is None:
            p_mode = proxy_mode if proxy_mode else "try"
            req_mode = "proxy" if proxy_list and len(proxy_list) > 0 else "direct"
            self.proxy_config = ProxyConfig(
                proxy_mode=p_mode, proxy_list=proxy_list, request_mode=req_mode
            )
        else:
            self.proxy_config = proxy_config

        if not show_log:
            logger.setLevel("CRITICAL")

    @optimize_execution("TCBS")
    def scan(
        self,
        filters: Optional[List[Dict[str, Any]]] = None,
        page: int = 0,
        size: int = 100,
        asset_type: str = "STOCK",
        show_log: Optional[bool] = False,
        get_all: bool = False,
    ) -> pd.DataFrame:
        """
        Lọc cổ phiếu theo điều kiện từ TCBS (thực nghiệm).

        Endpoint: POST /ligo/v1/watchlist/preview

        Args:
            filters: Danh sách điều kiện lọc. Mặc định None (lấy tất cả).
            page: Trang dữ liệu (0-based). Mặc định 0.
            size: Số bản ghi mỗi trang. Mặc định 100.
            asset_type: Loại tài sản ('STOCK', 'INDEX'). Mặc định 'STOCK'.
            show_log: Hiển thị log debug.
            get_all: Trả về tất cả cột bao gồm vendor signal fields.
                     Mặc định False (chỉ symbol, exchange, industry).

        Returns:
            DataFrame kết quả lọc. Tối thiểu: symbol, exchange, industry.
            Nếu get_all=True: thêm các trường vendor từ TCBS.

        Note:
            EXPERIMENTAL: Endpoint này không chính thức và có thể thay đổi.
            Vendor signal fields (signal, recommendation) là dữ liệu thô từ TCBS,
            không phải lời khuyên đầu tư.
        """
        payload = {
            "page": page,
            "size": size,
            "type": asset_type,
            "filter": filters or [],
        }

        # Build headers with Content-Type for POST
        post_headers = dict(self.headers)
        post_headers["Content-Type"] = "application/json"

        json_data = send_request(
            url=_SCREENER_URL,
            headers=post_headers,
            method="POST",
            params=_json.dumps(payload),
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        if not json_data:
            return pd.DataFrame(columns=_SCREENER_STANDARD_COLUMNS)

        # Unwrap response
        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"] or []
        elif isinstance(json_data, list):
            records = json_data
        else:
            records = []

        if not records:
            return pd.DataFrame(columns=_SCREENER_STANDARD_COLUMNS)

        df = pd.DataFrame(records)

        # Normalize common field names
        col_map = {
            "ticker": "symbol",
            "t": "symbol",
            "sym": "symbol",
            "ex": "exchange",
            "ind": "industry",
            "industryEn": "industry",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        if not get_all:
            available_std = [c for c in _SCREENER_STANDARD_COLUMNS if c in df.columns]
            df = df[available_std]
        else:
            # Rename vendor signal fields for clarity
            vendor_rename = {}
            for col in df.columns:
                if col.lower() in ("signal", "recommendation", "rating", "targetprice"):
                    vendor_rename[col] = f"vendor_{col.lower()}"
            if vendor_rename:
                df = df.rename(columns=vendor_rename)

        df.attrs["source"] = self.data_source
        df.attrs["experimental"] = True
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()

        if show_log or self.show_log:
            logger.info(f"Truy xuất thành công {len(df)} kết quả screener từ TCBS.")

        return df


# Register TCBS Screener provider
ProviderRegistry.register("screener", "tcbs", Screener)
