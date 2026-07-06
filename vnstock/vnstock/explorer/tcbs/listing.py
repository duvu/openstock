"""Listing / Symbol Industry module for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Read-only market listing and symbol industry classification data.
No broker, account, order, iCopy, margin, or transfer endpoints.
TCBS is NOT the default provider — pass source='tcbs' explicitly.
Classification system: TCBS_INTERNAL (proprietary, not ICB).
Unofficial public endpoints — may drift without notice.
"""

from datetime import datetime
from typing import List, Optional

import pandas as pd
from vnai import optimize_execution

from vnstock.core.registry import ProviderRegistry  # noqa: F401
from vnstock.core.utils.client import ProxyConfig, send_request
from vnstock.core.utils.logger import get_logger
from vnstock.core.utils.user_agent import get_headers
from vnstock.explorer.tcbs.auth import TCBSAuth
from vnstock.explorer.tcbs.const import (
    _BASE_URL,
    _COMPANY_TICKER_OVERVIEW_URL,
)

logger = get_logger(__name__)

# Listing / symbols endpoint
_SYMBOLS_URL = f"{_BASE_URL}/stock-insight/v1/symbol/all"


class Listing:
    """
    Lớp truy cập danh sách mã chứng khoán và phân loại ngành từ TCBS.

    Endpoint: /stock-insight/v1/symbol/all

    Classification system: TCBS_INTERNAL (hệ thống phân loại nội bộ TCBS,
    không phải tiêu chuẩn ICB).

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
        Khởi tạo Listing client cho TCBS.

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

    def _fetch(self, url: str, params: Optional[dict] = None, show_log: bool = False):
        """Internal helper: send request and return raw JSON."""
        return send_request(
            url=url,
            headers=self.headers,
            method="GET",
            params=params,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

    @optimize_execution("TCBS")
    def all_symbols(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách tất cả mã chứng khoán từ TCBS.

        Endpoint: /stock-insight/v1/symbol/all

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame danh sách tất cả mã chứng khoán.
        """
        json_data = self._fetch(_SYMBOLS_URL, show_log=show_log)

        if not json_data:
            return pd.DataFrame()

        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"] or []
        elif isinstance(json_data, list):
            records = json_data
        else:
            records = []

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def symbols_by_industries(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất phân loại ngành cho các mã chứng khoán từ TCBS.

        Sử dụng dữ liệu từ /stock-insight/v1/symbol/all với các trường ngành.
        Hệ thống phân loại: TCBS_INTERNAL (không phải ICB).

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame với các cột: symbol, provider, classification_system,
            industry_code, industry_name, fetched_at.
        """
        df = self.all_symbols(show_log=show_log)

        if df.empty:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "provider",
                    "classification_system",
                    "industry_code",
                    "industry_name",
                    "fetched_at",
                ]
            )

        # Normalize field names — TCBS may use different field names
        col_map = {
            "ticker": "symbol",
            "sym": "symbol",
            "industryId": "industry_code",
            "industry": "industry_name",
            "industryEn": "industry_name",
            "industryIdV2": "industry_code_v2",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # Add metadata columns
        df["provider"] = "TCBS"
        df["classification_system"] = "TCBS_INTERNAL"
        df["fetched_at"] = datetime.utcnow().isoformat()

        # Select output columns
        output_cols = ["symbol", "provider", "classification_system"]
        for col in ["industry_code", "industry_name", "industry_code_v2", "fetched_at"]:
            if col in df.columns:
                output_cols.append(col)

        available = [c for c in output_cols if c in df.columns]
        result = df[available].copy()
        result.attrs["source"] = self.data_source
        result.attrs["fetched_at"] = df.attrs.get(
            "fetched_at", datetime.utcnow().isoformat()
        )
        return result

    @optimize_execution("TCBS")
    def symbol_industry(
        self,
        symbol: str,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất thông tin ngành của một mã chứng khoán cụ thể từ TCBS.

        Sử dụng endpoint /tcanalysis/v1/ticker/{symbol}/overview.

        Args:
            symbol: Mã chứng khoán (VD: 'FPT').
            show_log: Hiển thị log debug.

        Returns:
            DataFrame với: symbol, provider, classification_system=TCBS_INTERNAL,
            industry_code, industry_name, fetched_at.
        """
        symbol = symbol.upper()
        url = _COMPANY_TICKER_OVERVIEW_URL.format(symbol=symbol)
        json_data = self._fetch(url, show_log=show_log)

        if not json_data:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "provider",
                    "classification_system",
                    "industry_code",
                    "industry_name",
                    "fetched_at",
                ]
            )

        if isinstance(json_data, dict):
            raw = json_data
        elif isinstance(json_data, list) and json_data:
            raw = json_data[0]
        else:
            raw = {}

        record = {
            "symbol": symbol,
            "provider": "TCBS",
            "classification_system": "TCBS_INTERNAL",
            "industry_code": raw.get("industryId", raw.get("industry_id", None)),
            "industry_name": raw.get("industry", raw.get("industryEn", None)),
            "industry_code_v2": raw.get("industryIdV2", None),
            "fetched_at": datetime.utcnow().isoformat(),
        }

        df = pd.DataFrame([record])
        df.attrs["symbol"] = symbol
        df.attrs["source"] = self.data_source
        return df


# Register TCBS Listing provider
ProviderRegistry.register("listing", "tcbs", Listing)
