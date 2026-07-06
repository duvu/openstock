"""Company module for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Read-only company fundamental data (overview, shareholders, officers, etc.).
No broker, account, order, iCopy, margin, or transfer endpoints.
TCBS is NOT the default provider — pass source='tcbs' explicitly.
Vendor-derived fields (ratings, signals) are raw data, NOT investment advice.
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
    _COMPANY_ACTIVITY_NEWS_URL,
    _COMPANY_DIVIDENDS_URL,
    _COMPANY_EVENTS_NEWS_URL,
    _COMPANY_INSIDER_DEALING_URL,
    _COMPANY_OFFICERS_URL,
    _COMPANY_OVERVIEW_COLUMNS,
    _COMPANY_OVERVIEW_MAP,
    _COMPANY_OVERVIEW_URL,
    _COMPANY_SHAREHOLDERS_URL,
    _COMPANY_SUBSIDIARIES_URL,
    _COMPANY_TICKER_OVERVIEW_URL,
)

logger = get_logger(__name__)


def _normalize_overview(raw: dict, symbol: str) -> dict:
    """Normalize raw TCBS company overview response to standard schema."""
    normalized = {}
    for raw_key, norm_key in _COMPANY_OVERVIEW_MAP.items():
        if raw_key in raw and norm_key not in normalized:
            normalized[norm_key] = raw[raw_key]

    # Ensure symbol is always set
    if "symbol" not in normalized:
        normalized["symbol"] = symbol.upper()

    return normalized


class Company:
    """
    Lớp truy cập dữ liệu công ty từ TCBS.

    Các endpoint:
    - overview: /tcanalysis/v1/ticker/{symbol}/overview + /tcanalysis/v1/company/{symbol}/overview
    - shareholders: /tcanalysis/v1/company/{symbol}/large-share-holders
    - insider_deals: /tcanalysis/v1/company/{symbol}/insider-dealing
    - subsidiaries: /stock-insight/v1/company/{symbol}/subsidiaries
    - officers: /stock-insight/v1/company/{symbol}/officers
    - events: /tcanalysis/v1/ticker/{symbol}/events-news
    - news: /tcanalysis/v1/ticker/{symbol}/activity-news
    - dividends: /stock-insight/v1/company/{symbol}/dividends

    TCBS là nguồn dữ liệu không chính thức — không đặt làm mặc định.
    """

    def __init__(
        self,
        symbol: str = None,
        token: Optional[str] = None,
        random_agent: bool = False,
        to_df: Optional[bool] = True,
        show_log: Optional[bool] = False,
        proxy_config: Optional[ProxyConfig] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """
        Khởi tạo Company client cho TCBS.

        Args:
            symbol: Mã chứng khoán (VD: 'FPT', 'VCB').
            token: Bearer token TCBS. Nếu None, tự động tải từ
                   TCBS_BEARER_TOKEN env var hoặc ~/.config/vnstock/tcbs_token.json.
            random_agent: Sử dụng user agent ngẫu nhiên. Mặc định False.
            to_df: Trả về DataFrame. Mặc định True.
            show_log: Hiển thị log debug. Mặc định False.
            proxy_config: Cấu hình proxy. Mặc định None.
            proxy_mode: Chế độ proxy. Mặc định None.
            proxy_list: Danh sách proxy URLs. Mặc định None.
        """
        self.symbol = symbol.upper() if symbol else ""
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
        self.to_df = to_df

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

    def _fetch(
        self,
        url: str,
        params: Optional[dict] = None,
        method: str = "GET",
        show_log: bool = False,
    ):
        """Internal helper: send request and return raw JSON."""
        return send_request(
            url=url,
            headers=self.headers,
            method=method,
            params=params,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

    def _records_from_response(self, json_data) -> list:
        """Extract record list from various TCBS response shapes."""
        if not json_data:
            return []
        if isinstance(json_data, dict) and "data" in json_data:
            return json_data["data"] or []
        if isinstance(json_data, list):
            return json_data
        # Single-object response — wrap in list
        if isinstance(json_data, dict):
            return [json_data]
        return []

    @optimize_execution("TCBS")
    def overview(
        self,
        show_log: Optional[bool] = False,
        get_all: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất thông tin tổng quan công ty từ TCBS.

        Kết hợp dữ liệu từ:
        - /tcanalysis/v1/ticker/{symbol}/overview
        - /tcanalysis/v1/company/{symbol}/overview

        Args:
            show_log: Hiển thị log debug.
            get_all: Trả về tất cả các trường. Mặc định False (chỉ normalized columns).

        Returns:
            DataFrame với thông tin công ty theo schema chuẩn.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức overview().")

        # Fetch ticker-level overview
        ticker_url = _COMPANY_TICKER_OVERVIEW_URL.format(symbol=self.symbol)
        ticker_data = self._fetch(ticker_url, show_log=show_log) or {}

        # Fetch company-level overview
        company_url = _COMPANY_OVERVIEW_URL.format(symbol=self.symbol)
        company_data = self._fetch(company_url, show_log=show_log) or {}

        # Merge both responses (ticker_data takes precedence)
        merged = {}
        if isinstance(company_data, dict):
            merged.update(company_data)
        if isinstance(ticker_data, dict):
            merged.update(ticker_data)

        if not merged:
            return pd.DataFrame(columns=_COMPANY_OVERVIEW_COLUMNS)

        normalized = _normalize_overview(merged, self.symbol)

        if get_all:
            # Return all fields from both responses
            all_data = {**merged, **normalized}
            df = pd.DataFrame([all_data])
        else:
            df = pd.DataFrame([normalized])
            available = [c for c in _COMPANY_OVERVIEW_COLUMNS if c in df.columns]
            df = df[available]

        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()

        return df

    @optimize_execution("TCBS")
    def shareholders(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách cổ đông lớn từ TCBS.

        Endpoint: /tcanalysis/v1/company/{symbol}/large-share-holders

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame danh sách cổ đông lớn.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức shareholders().")

        url = _COMPANY_SHAREHOLDERS_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def insider_deals(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất giao dịch nội bộ từ TCBS.

        Endpoint: /tcanalysis/v1/company/{symbol}/insider-dealing

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame giao dịch nội bộ.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức insider_deals().")

        url = _COMPANY_INSIDER_DEALING_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def subsidiaries(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách công ty con từ TCBS.

        Endpoint: /stock-insight/v1/company/{symbol}/subsidiaries

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame danh sách công ty con/liên kết.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức subsidiaries().")

        url = _COMPANY_SUBSIDIARIES_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def officers(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất danh sách ban lãnh đạo từ TCBS.

        Endpoint: /stock-insight/v1/company/{symbol}/officers

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame danh sách lãnh đạo công ty.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức officers().")

        url = _COMPANY_OFFICERS_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def events(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất sự kiện doanh nghiệp từ TCBS.

        Endpoint: /tcanalysis/v1/ticker/{symbol}/events-news

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame danh sách sự kiện doanh nghiệp.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức events().")

        url = _COMPANY_EVENTS_NEWS_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def news(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất tin tức hoạt động doanh nghiệp từ TCBS.

        Endpoint: /tcanalysis/v1/ticker/{symbol}/activity-news

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame tin tức hoạt động doanh nghiệp.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức news().")

        url = _COMPANY_ACTIVITY_NEWS_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def dividends(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Truy xuất lịch sử cổ tức từ TCBS.

        Endpoint: /stock-insight/v1/company/{symbol}/dividends

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame lịch sử cổ tức.
        """
        if not self.symbol:
            raise ValueError("symbol là bắt buộc cho phương thức dividends().")

        url = _COMPANY_DIVIDENDS_URL.format(symbol=self.symbol)
        json_data = self._fetch(url, show_log=show_log)
        records = self._records_from_response(json_data)

        df = pd.DataFrame(records) if records else pd.DataFrame()
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    # Alias for backward-compat with VCI/KBS Company interface
    def info(self, *args, **kwargs) -> pd.DataFrame:
        """Alias for overview()."""
        return self.overview(*args, **kwargs)


# Register TCBS Company provider
ProviderRegistry.register("company", "tcbs", Company)
