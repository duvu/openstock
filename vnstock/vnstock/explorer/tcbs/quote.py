"""Quote module for TCBS data source.

SCOPE / SAFETY GATE
-------------------
Read-only OHLCV and intraday tick data only.  No broker/account/order endpoints.
TCBS is NOT the default provider — pass source='tcbs' explicitly.
Unofficial public endpoints — may drift without notice.
"""

import json as _json
from datetime import datetime, timezone
from typing import List, Optional, Union

import pandas as pd
from vnai import optimize_execution

from vnstock.core.registry import ProviderRegistry  # noqa: F401
from vnstock.core.utils.client import ProxyConfig, send_request
from vnstock.core.utils.logger import get_logger
from vnstock.core.utils.lookback import (
    get_start_date_from_lookback,
    interpret_lookback_length,
)
from vnstock.core.utils.user_agent import get_headers
from vnstock.explorer.tcbs.auth import TCBSAuth
from vnstock.explorer.tcbs.const import (
    _INTERVAL_MAP,
    _INTRADAY_CORE_COLUMNS,
    _INTRADAY_MAP,
    _INTRADAY_URL,
    _OHLC_DTYPE,
    _OHLC_MAP,
    _OHLCV_URLS,
)

logger = get_logger(__name__)


def _to_unix_timestamp(date_str: str) -> int:
    """Convert YYYY-MM-DD to Unix epoch seconds (UTC midnight)."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError as e:
        raise ValueError(
            f"Ngày không hợp lệ: {date_str}. Định dạng yêu cầu: YYYY-MM-DD"
        ) from e


class Quote:
    """
    Lớp truy cập dữ liệu giá lịch sử từ TCBS.

    Endpoints: /stock/v2/stock/bars-long-term (primary),
    /stock-insight/v2/stock/bars-long-term, /stock-insight/v1/stock/bars-long-term
    (fallback in order).

    TCBS là nguồn dữ liệu không chính thức — không đặt làm mặc định.
    """

    def __init__(
        self,
        symbol: str,
        token: Optional[str] = None,
        random_agent: Optional[bool] = False,
        proxy_config: Optional[ProxyConfig] = None,
        show_log: Optional[bool] = False,
        proxy_mode: Optional[str] = None,
        proxy_list: Optional[List[str]] = None,
    ):
        """
        Khởi tạo Quote client cho TCBS.

        Args:
            symbol: Mã chứng khoán (VD: 'FPT', 'VCB').
            token: Bearer token TCBS. Nếu None, tự động tải từ
                   TCBS_BEARER_TOKEN env var hoặc ~/.config/vnstock/tcbs_token.json.
                   Chạy ``vnstock-tcbs-login`` để lấy token.
            random_agent: Sử dụng user agent ngẫu nhiên. Mặc định False.
            proxy_config: Cấu hình proxy. Mặc định None.
            show_log: Hiển thị log debug. Mặc định False.
            proxy_mode: Chế độ proxy. Mặc định None.
            proxy_list: Danh sách proxy URLs. Mặc định None.
        """
        self.symbol = symbol.upper()
        self.data_source = "TCBS"

        # Resolve bearer token
        _token = token or TCBSAuth.load_token()
        self.headers = get_headers(
            data_source=self.data_source, random_agent=random_agent
        )
        if _token:
            self.headers["Authorization"] = f"Bearer {_token}"
        else:
            logger.warning(
                "Không tìm thấy TCBS token. Chạy `vnstock-tcbs-login` hoặc đặt "
                "TCBS_BEARER_TOKEN để truy cập dữ liệu. "
                "Các yêu cầu không có token sẽ thất bại (HTTP 401)."
            )

        self.show_log = show_log
        self.interval_map = _INTERVAL_MAP

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
    def history(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
        interval: Optional[str] = "1D",
        to_df: Optional[bool] = True,
        show_log: Optional[bool] = False,
        count_back: Optional[int] = None,
        floating: Optional[int] = 2,
        length: Optional[Union[str, int]] = None,
        get_all: Optional[bool] = False,
    ) -> Union[pd.DataFrame, str]:
        """
        Tải lịch sử giá của mã chứng khoán từ TCBS.

        Thử tuần tự: /stock/v2/stock/bars-long-term →
        /stock-insight/v2/stock/bars-long-term →
        /stock-insight/v1/stock/bars-long-term

        Args:
            start: Ngày bắt đầu (YYYY-MM-DD). Bắt buộc nếu không có length/count_back.
            end: Ngày kết thúc (YYYY-MM-DD). Mặc định hôm nay.
            interval: Khung thời gian. Nhận: 1m, 5m, 15m, 30m, 1H, 1D, 1W, 1M.
            to_df: Trả về DataFrame. Mặc định True.
            show_log: Hiển thị log debug.
            count_back: Số lượng nến cần lấy.
            floating: Số chữ số thập phân. Mặc định 2.
            length: Khoảng thời gian phân tích (vd: '3M', 150, '100b').
            get_all: Lấy tất cả cột. Mặc định False.

        Returns:
            DataFrame với cột [time, open, high, low, close, volume].
        """
        if end is None:
            end = datetime.now().strftime("%Y-%m-%d")

        if start is None:
            if length is not None:
                bars_from_len, len_remainder = interpret_lookback_length(length)
                if bars_from_len is not None:
                    count_back = bars_from_len
                    length = None
                else:
                    length = len_remainder

            if length is not None:
                start = get_start_date_from_lookback(
                    lookback_length=length, end_date=end
                )
            elif count_back is not None:
                start = get_start_date_from_lookback(
                    bars=count_back, interval=interval, end_date=end
                )
            else:
                raise ValueError(
                    "Tham số 'start' là bắt buộc nếu không cung cấp 'length' hoặc 'count_back'."
                )

        if interval not in self.interval_map:
            valid_intervals = ", ".join(self.interval_map.keys())
            raise ValueError(
                f"Giá trị interval không hợp lệ: {interval}. Vui lòng chọn: {valid_intervals}"
            )

        resolution = self.interval_map[interval]
        from_ts = _to_unix_timestamp(start)
        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(f"Ngày kết thúc không hợp lệ: {end}") from e

        to_ts = int(
            end_dt.replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            ).timestamp()
        )

        params = {
            "ticker": self.symbol,
            "type": "stock",
            "resolution": resolution,
            "from": from_ts,
            "to": to_ts,
        }

        # Try endpoints in fallback order
        json_data = None
        last_error: Optional[Exception] = None
        for url in _OHLCV_URLS:
            try:
                result = send_request(
                    url=url,
                    headers=self.headers,
                    method="GET",
                    params=params,
                    show_log=show_log or self.show_log,
                    proxy_list=self.proxy_config.proxy_list,
                    proxy_mode=self.proxy_config.proxy_mode,
                    request_mode=self.proxy_config.request_mode,
                )
                if result:
                    json_data = result
                    endpoint_used = url
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if show_log or self.show_log:
                    logger.warning(f"TCBS endpoint {url} failed: {exc}. Trying next.")

        if not json_data:
            if last_error:
                raise ValueError(
                    f"Không tìm thấy dữ liệu cho mã {self.symbol} từ TCBS. Lỗi cuối: {last_error}"
                ) from last_error
            raise ValueError(
                f"Không tìm thấy dữ liệu cho mã {self.symbol} từ TCBS. "
                "Vui lòng kiểm tra lại mã chứng khoán hoặc khoảng thời gian."
            )

        # TCBS returns {"data": [...]} or array of {t, o, h, l, c, v}
        if isinstance(json_data, dict) and "data" in json_data:
            raw_records = json_data["data"]
        elif isinstance(json_data, dict) and "t" in json_data:
            # Array-of-arrays format (same as KBS/DNSE)
            length_data = len(json_data["t"])
            raw_records = []
            for i in range(length_data):
                raw_records.append(
                    {
                        "t": json_data["t"][i],
                        "o": json_data.get("o", [None] * length_data)[i],
                        "h": json_data.get("h", [None] * length_data)[i],
                        "l": json_data.get("l", [None] * length_data)[i],
                        "c": json_data.get("c", [None] * length_data)[i],
                        "v": json_data.get("v", [0] * length_data)[i],
                    }
                )
        elif isinstance(json_data, list):
            raw_records = json_data
        else:
            raise ValueError(
                f"Định dạng dữ liệu không được nhận dạng từ TCBS cho {self.symbol}."
            )

        if not raw_records:
            raise ValueError(
                f"Dữ liệu trống cho mã {self.symbol} với interval {interval}."
            )

        if not to_df:
            return _json.dumps(raw_records)

        df = pd.DataFrame(raw_records)

        if df.empty:
            raise ValueError(
                f"Dữ liệu trống cho mã {self.symbol} với interval {interval}."
            )

        # Rename columns
        df = df.rename(columns=_OHLC_MAP)

        # Keep only standard columns unless get_all
        if not get_all:
            base_cols = ["time", "open", "high", "low", "close", "volume"]
            df = df[[c for c in base_cols if c in df.columns]]

        # Convert time: TCBS returns Unix epoch seconds → datetime (Asia/Ho_Chi_Minh)
        if "time" in df.columns:
            try:
                df["time"] = (
                    pd.to_datetime(df["time"], unit="s", utc=True)
                    .dt.tz_convert("Asia/Ho_Chi_Minh")
                    .dt.tz_localize(None)
                )
            except Exception:
                pass

        # Apply dtypes
        for col, dtype in _OHLC_DTYPE.items():
            if col in df.columns and col != "time":
                try:
                    df[col] = df[col].astype(dtype)
                except (ValueError, TypeError):
                    pass

        # Round prices
        price_cols = ["open", "high", "low", "close"]
        if floating is not None:
            for col in price_cols:
                if col in df.columns:
                    df[col] = df[col].round(floating)

        # Metadata
        df.attrs["symbol"] = self.symbol
        df.attrs["source"] = self.data_source
        df.attrs["interval"] = interval
        df.attrs["start"] = start
        df.attrs["end"] = end
        df.attrs["endpoint_variant"] = endpoint_used
        df.attrs["fetched_at"] = datetime.utcnow().isoformat()

        if show_log or self.show_log:
            logger.info(
                f"Truy xuất thành công {len(df)} bản ghi OHLCV cho {self.symbol} "
                f"({interval}, {start} → {end}) từ {endpoint_used}."
            )

        return df

    @optimize_execution("TCBS")
    def intraday(
        self,
        date: Optional[str] = None,
        page: Optional[int] = 0,
        size: Optional[int] = 100,
        to_df: Optional[bool] = True,
        show_log: Optional[bool] = False,
        get_all: Optional[bool] = False,
    ) -> Union[pd.DataFrame, str]:
        """
        Tải dữ liệu khớp lệnh intraday từ TCBS (thực nghiệm).

        Endpoint: /stock/v1/intraday/{symbol}/his/paging

        Args:
            date: Ngày giao dịch (YYYY-MM-DD). Mặc định hôm nay.
            page: Trang dữ liệu (0-based). Mặc định 0.
            size: Số bản ghi mỗi trang. Mặc định 100.
            to_df: Trả về DataFrame. Mặc định True.
            show_log: Hiển thị log debug.
            get_all: Lấy thêm các cột mở rộng. Mặc định False.

        Returns:
            DataFrame với cột [time, price, volume, match_type, id].

        Note:
            Đây là endpoint thực nghiệm — cấu trúc có thể thay đổi.
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        try:
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError(
                f"Ngày không hợp lệ: {date}. Định dạng yêu cầu: YYYY-MM-DD"
            ) from e

        url = _INTRADAY_URL.format(symbol=self.symbol)
        params = {"page": page, "size": size}

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
            if to_df:
                return pd.DataFrame(columns=_INTRADAY_CORE_COLUMNS)
            return "[]"

        # Unwrap response
        if isinstance(json_data, dict) and "data" in json_data:
            records = json_data["data"]
        elif isinstance(json_data, list):
            records = json_data
        else:
            records = []

        if not records:
            if to_df:
                return pd.DataFrame(columns=_INTRADAY_CORE_COLUMNS)
            return "[]"

        if not to_df:
            return _json.dumps(records)

        df = pd.DataFrame(records)
        df = df.rename(columns=_INTRADAY_MAP)

        # Normalize match_type
        if "match_type" in df.columns:
            df["match_type"] = (
                df["match_type"]
                .fillna("")
                .astype(str)
                .str.upper()
                .map({"B": "buy", "S": "sell", "BU": "buy", "SD": "sell"})
                .fillna("unknown")
            )

        # Synthesize id if missing
        if "id" not in df.columns:
            time_col = df.get("time", pd.Series(range(len(df))))
            price_col = df.get("price", pd.Series([0.0] * len(df)))
            vol_col = df.get("volume", pd.Series([0] * len(df)))
            df["id"] = (
                time_col.astype(str).str.replace(" ", "_").str.replace(":", "")
                + "_"
                + price_col.astype(str).str.replace(".", "")
                + "_"
                + vol_col.astype(str)
            )

        if get_all:
            result_df = df
        else:
            existing_core = [c for c in _INTRADAY_CORE_COLUMNS if c in df.columns]
            result_df = df[existing_core]

        result_df = result_df.copy()
        result_df.attrs["symbol"] = self.symbol
        result_df.attrs["source"] = self.data_source
        result_df.attrs["date"] = date
        result_df.attrs["fetched_at"] = datetime.utcnow().isoformat()

        if show_log or self.show_log:
            logger.info(
                f"Truy xuất thành công {len(result_df)} bản ghi intraday TCBS cho {self.symbol}."
            )

        return result_df


# Register TCBS Quote provider
ProviderRegistry.register("quote", "tcbs", Quote)
