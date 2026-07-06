"""Trading / Price Board module for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Read-only price board (market snapshot) data only.
No broker, account, order, iCopy, margin, or transfer endpoints.
TCBS is NOT the default provider — pass source='tcbs' explicitly.
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
    _PRICE_BOARD_MAP,
    _PRICE_BOARD_STANDARD_COLUMNS,
    _PRICE_BOARD_URL,
)

logger = get_logger(__name__)


class Trading:
    """
    Lớp truy cập dữ liệu bảng giá từ TCBS.

    Endpoint: /stock/v1/stock/second-tc-price?tickers=FPT,VCB

    TCBS là nguồn dữ liệu không chính thức — không đặt làm mặc định.
    """

    def __init__(
        self,
        symbol: Optional[str] = None,
        token: Optional[str] = None,
        random_agent: Optional[bool] = False,
        proxy_config: Optional[ProxyConfig] = None,
        show_log: Optional[bool] = False,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """
        Khởi tạo Trading client cho TCBS.

        Args:
            symbol: Mã chứng khoán. Optional cho market-wide queries.
            token: Bearer token TCBS. Nếu None, tự động tải từ
                   TCBS_BEARER_TOKEN env var hoặc ~/.config/vnstock/tcbs_token.json.
            random_agent: Sử dụng user agent ngẫu nhiên. Mặc định False.
            proxy_config: Cấu hình proxy. Mặc định None.
            show_log: Hiển thị log debug. Mặc định False.
            proxy_mode: Chế độ proxy. Mặc định None.
            proxy_list: Danh sách proxy URLs. Mặc định None.
        """
        self.symbol = symbol.upper() if symbol else None
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
    def price_board(
        self,
        symbols_list: List[str],
        show_log: Optional[bool] = False,
        get_all: bool = False,
    ) -> pd.DataFrame:
        """
        Truy xuất bảng giá realtime cho danh sách mã chứng khoán từ TCBS.

        Endpoint: /stock/v1/stock/second-tc-price?tickers=FPT,VCB

        Args:
            symbols_list: Danh sách mã chứng khoán (VD: ['FPT', 'VCB']).
            show_log: Hiển thị log debug. Mặc định False.
            get_all: Giữ tất cả cột từ API response. Mặc định False.

        Returns:
            DataFrame với thông tin bảng giá cho các mã chứng khoán.
            Tối thiểu: symbol, close_price, volume_accumulated.
            Vendor-derived fields (ratings, signals) được đưa vào nếu get_all=True.

        Note:
            Các trường vendor (signal, rating) là dữ liệu thô từ TCBS, không phải
            lời khuyên đầu tư.

        Raises:
            ValueError: Nếu symbols_list rỗng.
        """
        if not symbols_list:
            raise ValueError("symbols_list không được để trống.")

        symbols_list = [s.upper() for s in symbols_list]
        tickers_param = ",".join(symbols_list)

        params = {"tickers": tickers_param}

        json_data = send_request(
            url=_PRICE_BOARD_URL,
            headers=self.headers,
            method="GET",
            params=params,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        if not json_data:
            df = pd.DataFrame()
            df.attrs["symbols"] = symbols_list
            df.attrs["source"] = self.data_source
            return df

        # Unwrap response
        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"]
        elif isinstance(json_data, list):
            records = json_data
        else:
            records = []

        df = pd.DataFrame(records) if records else pd.DataFrame()

        if not df.empty:
            df = df.rename(columns=_PRICE_BOARD_MAP)

            if not get_all:
                available_cols = [
                    c for c in _PRICE_BOARD_STANDARD_COLUMNS if c in df.columns
                ]
                df = df[available_cols]

        # Metadata
        df.attrs["symbols"] = symbols_list
        df.attrs["source"] = self.data_source
        df.attrs["get_all"] = get_all
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()

        if show_log or self.show_log:
            logger.info(
                f"Truy xuất thành công bảng giá TCBS cho {len(symbols_list)} mã chứng khoán."
            )

        return df


# Register TCBS Trading provider
ProviderRegistry.register("trading", "tcbs", Trading)
