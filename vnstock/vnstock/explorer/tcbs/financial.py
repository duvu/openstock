"""Financial (fundamental reports) module for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Read-only financial statement data (balance sheet, income statement,
cash flow, financial ratios).
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
    _FINANCE_URL,
    _FINANCIAL_PERIOD_MAP,
    _REPORT_TYPE_BALANCE_SHEET,
    _REPORT_TYPE_CASH_FLOW,
    _REPORT_TYPE_INCOME_STATEMENT,
    _REPORT_TYPE_RATIO,
)

logger = get_logger(__name__)


def _add_metadata_columns(
    df: pd.DataFrame,
    symbol: str,
    period: str,
    report_type: str,
    yearly: bool,
) -> pd.DataFrame:
    """Add normalized metadata columns to financial DataFrame."""
    df = df.copy()
    df["symbol"] = symbol
    df["period_type"] = "year" if yearly else "quarter"
    df["report_type"] = report_type
    df["provider"] = "TCBS"
    df["fetched_at"] = datetime.utcnow().isoformat()
    return df


class Finance:
    """
    Lớp truy cập dữ liệu báo cáo tài chính từ TCBS.

    Endpoint: /stock-insight/v1/finance/{symbol}/{report_type}?yearly=true|false&isAll=true

    Các loại báo cáo:
    - balance_sheet: balance-sheet
    - income_statement: income-statement
    - cash_flow: cash-flow
    - ratio: financialratio

    TCBS là nguồn dữ liệu không chính thức — không đặt làm mặc định.
    """

    def __init__(
        self,
        symbol: str,
        period: Optional[str] = "quarter",
        get_all: Optional[bool] = True,
        show_log: Optional[bool] = False,
        token: Optional[str] = None,
        proxy_config: Optional[ProxyConfig] = None,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """
        Khởi tạo Finance client cho TCBS.

        Args:
            symbol: Mã chứng khoán (VD: 'FPT', 'VCB').
            period: Kỳ báo cáo — 'year' hoặc 'quarter'. Mặc định 'quarter'.
            get_all: Lấy tất cả kỳ lịch sử (isAll=true). Mặc định True.
            show_log: Hiển thị log debug. Mặc định False.
            token: Bearer token TCBS. Nếu None, tự động tải từ
                   TCBS_BEARER_TOKEN env var hoặc ~/.config/vnstock/tcbs_token.json.
            proxy_config: Cấu hình proxy. Mặc định None.
            proxy_mode: Chế độ proxy. Mặc định None.
            proxy_list: Danh sách proxy URLs. Mặc định None.

        Raises:
            ValueError: Nếu period không hợp lệ.
        """
        if period not in ["year", "quarter"]:
            raise ValueError(
                "Kỳ báo cáo tài chính không hợp lệ. Chỉ chấp nhận 'year' hoặc 'quarter'."
            )

        self.symbol = symbol.upper()
        self.period = period
        self.yearly = _FINANCIAL_PERIOD_MAP[period]
        self.get_all = get_all
        self.data_source = "TCBS"

        _token = token or TCBSAuth.load_token()
        self.headers = get_headers(data_source=self.data_source)
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

    def _fetch_report(
        self,
        report_type: str,
        show_log: bool = False,
    ) -> pd.DataFrame:
        """Fetch a financial report from TCBS and return a raw DataFrame."""
        url = _FINANCE_URL.format(symbol=self.symbol, report_type=report_type)
        params = {
            "yearly": str(self.yearly).lower(),
            "isAll": str(self.get_all).lower(),
        }

        json_data = send_request(
            url=url,
            headers=self.headers,
            method="GET",
            params=params,
            show_log=show_log or self.show_log,
            proxy_list=self.proxy_config.proxy_list,
            proxy_mode=self.proxy_config.proxy_mode,
            request_mode=self.proxy_config.request_mode,
        )

        if not json_data:
            return pd.DataFrame()

        # TCBS finance responses: list of period dicts or {"data": [...]}
        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"] or []
        elif isinstance(json_data, list):
            records = json_data
        else:
            records = []

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = _add_metadata_columns(
            df, self.symbol, self.period, report_type, self.yearly
        )
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["report_type"] = report_type
        df.attrs["period"] = self.period
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()
        return df

    @optimize_execution("TCBS")
    def balance_sheet(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Tải bảng cân đối kế toán từ TCBS.

        Endpoint: /stock-insight/v1/finance/{symbol}/balance-sheet

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame bảng cân đối kế toán với các dòng mục TCBS gốc +
            metadata: symbol, period_type, report_type, provider, fetched_at.
        """
        return self._fetch_report(_REPORT_TYPE_BALANCE_SHEET, show_log=show_log)

    @optimize_execution("TCBS")
    def income_statement(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Tải báo cáo kết quả kinh doanh từ TCBS.

        Endpoint: /stock-insight/v1/finance/{symbol}/income-statement

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame báo cáo kết quả kinh doanh với các dòng mục TCBS gốc +
            metadata: symbol, period_type, report_type, provider, fetched_at.
        """
        return self._fetch_report(_REPORT_TYPE_INCOME_STATEMENT, show_log=show_log)

    @optimize_execution("TCBS")
    def cash_flow(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Tải báo cáo lưu chuyển tiền tệ từ TCBS.

        Endpoint: /stock-insight/v1/finance/{symbol}/cash-flow

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame báo cáo lưu chuyển tiền tệ với các dòng mục TCBS gốc +
            metadata: symbol, period_type, report_type, provider, fetched_at.
        """
        return self._fetch_report(_REPORT_TYPE_CASH_FLOW, show_log=show_log)

    @optimize_execution("TCBS")
    def ratio(
        self,
        show_log: Optional[bool] = False,
    ) -> pd.DataFrame:
        """
        Tải chỉ số tài chính từ TCBS.

        Endpoint: /stock-insight/v1/finance/{symbol}/financialratio

        Args:
            show_log: Hiển thị log debug.

        Returns:
            DataFrame chỉ số tài chính với các dòng mục TCBS gốc +
            metadata: symbol, period_type, report_type, provider, fetched_at.

        Note:
            Các chỉ số vendor (EPS, P/E, v.v.) là dữ liệu thô từ TCBS,
            không phải lời khuyên đầu tư.
        """
        return self._fetch_report(_REPORT_TYPE_RATIO, show_log=show_log)


# Register TCBS Finance provider
ProviderRegistry.register("finance", "tcbs", Finance)
