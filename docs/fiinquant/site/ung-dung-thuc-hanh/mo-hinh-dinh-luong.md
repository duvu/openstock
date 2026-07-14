# Mô hình định lượng

## 1. Tìm các điểm Pivot Point và Price Channel&#x20;

{% hint style="info" %}
Các điểm Pivot Point là mức giá quan trọng được tính toán dựa trên giá cao nhất (high), giá thấp nhất (low) và giá đóng cửa (close) của phiên giao dịch trước đó. Nó được sử dụng để xác định các mức hỗ trợ và kháng cự tiềm năng.\
\
Stock channel hay **kênh giá** là một phạm vi giá mà cổ phiếu dao động trong một khoảng thời gian nhất định. Kênh giá giúp xác định xu hướng hiện tại của thị trường. Có ba loại kênh giá phổ biến:

1. **Kênh giá tăng (Ascending Channel)** – Giá dao động trong một xu hướng tăng với mức đáy và đỉnh cao dần.
2. **Kênh giá giảm (Descending Channel)** – Giá dao động trong xu hướng giảm với mức đáy và đỉnh thấp dần.
3. **Kênh giá ngang (Sideways Channel)** – Giá dao động trong một phạm vi hẹp, không có xu hướng rõ ràng.

Kênh giá được xác định bằng hai đường trendline:

* **Trendline trên** kết nối các đỉnh
* **Trendline dưới** kết nối các đáy

Khi giá chạm vào đường trendline trên hoặc dưới, nó có thể phản ứng theo hai cách:

* **Bật ngược lại** nếu kênh giá tiếp tục giữ.
* **Phá vỡ (Breakout)** nếu xu hướng thay đổi, có thể dẫn đến sự hình thành một kênh giá mới.

Stock channels thường được sử dụng để tìm điểm vào lệnh mua ở vùng hỗ trợ và bán ở vùng kháng cự.
{% endhint %}

<figure><img src="/files/9EfR4HylUJB25SEjnmYz" alt=""><figcaption><p>Pivot Point (điểm màu tím)  trong dữ liệu lích sử giá của VCB </p></figcaption></figure>

**Lấy Historical data từ thư viện Fiinquant**

```python
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from scipy import stats
from FiinQuantX import FiinSession

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(
    username=username,
    password=password
).login()

data = client.Fetch_Trading_Data(
    tickers='VCB',
    fields=['open', 'high', 'low', 'close', 'volume'],
    adjusted=True,
    period=1000,
    realtime=False,
    by='1d',
).get_data()

```

**TÌm Pivot Point và plot giá cổ phiếu**

```python
# Function to identify pivot points in price data
# Returns: 0 for no pivot, 1 for pivot high, 2 for pivot low, 3 for both
# Parameters:
#   candle: index of the current candle being checked
#   window: number of candles to check on either side
def isPivot(candle, window):
    if candle-window < 0 or candle+window >= len(data):
        return 0
    
    pivotHigh = 1
    pivotLow = 2
    for i in range(candle-window, candle+window+1):
        if data.iloc[candle].low > data.iloc[i].low:
            pivotLow=0
        if data.iloc[candle].high < data.iloc[i].high:
            pivotHigh=0
    if (pivotHigh and pivotLow):
        return 3
    elif pivotHigh:
        return pivotHigh
    elif pivotLow:
        return pivotLow
    else:
        return 0

# Apply isPivot function to each row of data
window=10
data['isPivot'] = data.apply(lambda x: isPivot(x.name,window), axis=1)

# Function to determine plotting position for pivot points
# Returns slightly offset values for visual clarity on the chart
# Parameters:
#   x: row of dataframe containing price and pivot information
def pointpos(x):
    if x['isPivot']==2:
        return x['low']-1e-3  # Offset below pivot low
    elif x['isPivot']==1:
        return x['high']+1e-3 # Offset above pivot high
    else:
        return np.nan

# Apply pointpos function to create plotting positions
data['pointpos'] = data.apply(lambda row: pointpos(row), axis=1)


# Create candlestick chart
dfpl = data.copy()
fig = go.Figure(data=[go.Candlestick(x=dfpl.index,
                open=dfpl['open'],
                high=dfpl['high'],
                low=dfpl['low'],
                close=dfpl['close'])])

fig.add_scatter(x=dfpl.index, y=dfpl['pointpos'], mode="markers",
                marker=dict(size=5, color="MediumPurple"),
                name="pivot")
                
fig.update_layout(xaxis_rangeslider_visible=False)

fig.show()
```

**Tìm Price Channel dựa trên Pivot Point**&#x20;

<figure><img src="/files/u2Qtlfo085tyVC8DRh0Z" alt=""><figcaption><p>Một đoạn Sideway Channel </p></figcaption></figure>

```python
# Function to identify and calculate channel slopes using pivot points
# Parameters:
#   candle: Current candle position to analyze from
#   backcandles: Number of previous candles to look back
#   window: Window size for pivot point calculation
def collect_channel(candle, backcandles, window):
    # Get subset of data for analysis
    localdf = data[candle-backcandles-window:candle-window]
    localdf['isPivot'] = localdf.apply(lambda x: isPivot(x.name,window), axis=1)
    
    # Extract pivot highs and lows with their indices
    highs = localdf[localdf['isPivot']==1].high.values
    idxhighs = localdf[localdf['isPivot']==1].high.index
    lows = localdf[localdf['isPivot']==2].low.values
    idxlows = localdf[localdf['isPivot']==2].low.index
    
    # Calculate regression lines if enough pivot points exist
    if len(lows)>=2 and len(highs)>=2:
        # Calculate regression for lower channel (pivot lows)
        sl_lows, interc_lows, r_value_l, _, _ = stats.linregress(idxlows,lows)
        # Calculate regression for upper channel (pivot highs)
        sl_highs, interc_highs, r_value_h, _, _ = stats.linregress(idxhighs,highs)
    
        return(sl_lows, interc_lows, sl_highs, interc_highs, r_value_l**2, r_value_h**2)
    else:
        return(0,0,0,0,0,0)

# Set parameters for channel analysis
candle = 200          # Current candle position
backcandles = 100     # Number of candles to look back
window = 3            # Window size for pivot calculation

# Create candlestick chart
fig = go.Figure(data=[go.Candlestick(x=dfpl.index,
                open=dfpl['open'],
                high=dfpl['high'],
                low=dfpl['low'],
                close=dfpl['close'])])

# Add pivot points to chart
fig.add_scatter(x=dfpl.index, y=dfpl['pointpos'], mode="markers",
                marker=dict(size=5, color="MediumPurple"),
                name="pivot")

# Calculate channel slopes and angles
sl_lows, interc_lows, sl_highs, interc_highs, r_sq_l, r_sq_h = collect_channel(candle, backcandles, window)
print(sl_lows,sl_highs)
angle_lows = np.degrees(np.arctan(sl_lows))
angle_highs = np.degrees(np.arctan(sl_highs))

# Plot channel lines
x = np.array(range(candle-backcandles-window, candle+1))
fig.add_trace(go.Scatter(x=x, y=sl_lows*x + interc_lows, mode='lines', name='lower slope'))
fig.add_trace(go.Scatter(x=x, y=sl_highs*x + interc_highs, mode='lines', name='max slope'))
fig.update_layout(xaxis_rangeslider_visible=False)
fig.show()
```

## 2. Thống kê các giai đoạn tăng giá của VN-Index

Thông số có thể thay đổi:

Nếu đổi percent từ 5.0 lên 10.0 sẽ lọc những giai đoạn thị trường chỉnh nhiều hơn

```python
df["zigzag"] = zigzag_percent(df["high"], df["low"], df["close"], percent=5.0)
```

Fulll Code

```python
# Thống kê các giai đoạn giá tăng VNINDEX bằng ZigZag tự code (pivot chỉ tại điểm đảo chiều)
from FiinQuantX import FiinSession
import pandas as pd

# 1) Đăng nhập
client = FiinSession(username="YOUR_USER", password="YOUR_PASS").login()

# 2) Lấy dữ liệu VNINDEX (giá từ FiinQuant)
event = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VNINDEX"],
    fields=["high", "low", "close"],
    adjusted=True,
    by="1d",
    period=1500  # ~6 năm, tùy chỉnh
)
df = event.get_data().reset_index(drop=True)

# 3) ZigZag theo % đảo chiều: chỉ gắn pivot khi đảo chiều >= threshold
def zigzag_percent(high: pd.Series, low: pd.Series, close: pd.Series, percent: float = 5.0) -> pd.Series:
    thr = percent / 100.0
    n = len(close)
    pivots = [None] * n

    # Trạng thái
    trend = 0          # 0: chưa xác định, 1: up, -1: down
    start_idx = 0
    start_px = close.iloc[0]
    extreme_idx = 0    # chỉ số của đỉnh/đáy cực trị trong xu hướng hiện tại
    extreme_px = close.iloc[0]

    for i in range(1, n):
        px = close.iloc[i]

        if trend == 0:
            # Chờ giá đi đủ biên để xác nhận hướng ban đầu
            if px >= start_px * (1 + thr):
                trend = 1
                extreme_idx, extreme_px = i, px
            elif px <= start_px * (1 - thr):
                trend = -1
                extreme_idx, extreme_px = i, px
            else:
                # chưa đủ biên, tiếp tục theo dõi, cập nhật cực trị tạm
                if px > extreme_px:
                    extreme_idx, extreme_px = i, px
                if px < extreme_px:
                    extreme_idx, extreme_px = i, px
            continue

        if trend == 1:
            # Đang uptrend: cập nhật đỉnh cực trị
            if px > extreme_px:
                extreme_idx, extreme_px = i, px
            # Đảo chiều đủ biên → chốt pivot tại đỉnh cực trị trước đó
            elif px <= extreme_px * (1 - thr):
                pivots[extreme_idx] = extreme_px  # pivot tại reversal
                trend = -1
                extreme_idx, extreme_px = i, px   # bắt đầu theo dõi đáy mới
        else:  # trend == -1
            # Đang downtrend: cập nhật đáy cực trị
            if px < extreme_px:
                extreme_idx, extreme_px = i, px
            # Đảo chiều đủ biên → chốt pivot tại đáy cực trị trước đó
            elif px >= extreme_px * (1 + thr):
                pivots[extreme_idx] = extreme_px
                trend = 1
                extreme_idx, extreme_px = i, px

    # Chốt pivot cuối cùng tại cực trị hiện tại (tùy chọn)
    pivots[extreme_idx] = extreme_px
    return pd.Series(pivots, index=close.index, name="zigzag")

# 4) Áp dụng ZigZag và tạo bảng các đoạn TĂNG
df["zigzag"] = zigzag_percent(df["high"], df["low"], df["close"], percent=5.0)

turn_points = df.dropna(subset=["zigzag"]).reset_index()  # chỉ còn các pivot tại điểm đảo chiều
uptrends = []

for i in range(1, len(turn_points)):
    i0 = turn_points.loc[i-1, "index"]
    i1 = turn_points.loc[i, "index"]
    p0 = turn_points.loc[i-1, "zigzag"]
    p1 = turn_points.loc[i, "zigzag"]

    if p1 > p0:  # đoạn tăng là từ pivot đáy → pivot đỉnh tiếp theo
        uptrends.append({
            "StartIndex": i0,
            "EndIndex": i1,
            "StartDate": df.loc[i0, "timestamp"],
            "EndDate": df.loc[i1, "timestamp"],
            "LengthInBars": i1 - i0,
            "StartPrice": float(p0),
            "EndPrice": float(p1),
            "PctChange": (p1 - p0) / p0 * 100.0
        })

uptrend_df = pd.DataFrame(uptrends)
# Ví dụ lọc các đợt tăng đủ dài và mạnh
# uptrend_df = uptrend_df[(uptrend_df["LengthInBars"] >= 20) & (uptrend_df["PctChange"] >= 10)]

print(uptrend_df.sort_values("StartIndex").reset_index(drop=True))
```

## 3. Thống kê diễn biến các phiên trước nghỉ lễ

```python
from FiinQuantX import FiinSession
import pandas as pd
from datetime import datetime, timedelta

client = FiinSession(username= 'USERNAME', password='PASSWORD').login()
# Hàm truy xuất 10 phiên trước 2/9 của mỗi năm
def get_last_sessions_before_sep2(year, n=10):
    to_date = f"{year}-09-01"
    from_date = (datetime.strptime(to_date, "%Y-%m-%d") - timedelta(days=30)).strftime("%Y-%m-%d")

    event = client.Fetch_Trading_Data(
        realtime=False,
        tickers=["VNINDEX"],
        fields=["close"],
        adjusted=True,
        by="1d",
        from_date=from_date,
        to_date=to_date
    )
    df = event.get_data().sort_values("timestamp").reset_index(drop=True)
    df = df.tail(n).copy()
    df["return"] = df["close"].pct_change() * 100  # Tính % thay đổi
    df["label"] = [f"T-{i}" for i in reversed(range(1, n + 1))]
    df["year"] = year
    return df[["year", "label", "timestamp", "close", "return"]]

# Gom dữ liệu 10 năm gần nhất
all_data = []
for y in range(datetime.today().year - 10, datetime.today().year):
    df = get_last_sessions_before_sep2(y)
    all_data.append(df)

# Kết quả
final_df = pd.concat(all_data).reset_index(drop=True)

# Pivot để tạo bảng
pivot_table = final_df.pivot(index="year", columns="label", values="close")
returns_table = final_df.pivot(index="year", columns="label", values="return")

print("==== Giá đóng cửa (Close) ====")
print(pivot_table.round(2))

print("\n==== Tỷ suất sinh lời hàng ngày (%) ====")
print(returns_table.round(2))
```

## 4. Thống kê số lượng mã cổ phiếu cắt lên và cắt xuống đường MA20

```python
import pandas as pd
import numpy as np
from FiinQuantX import FiinSession
from datetime import datetime, timedelta

# Bước 1: Login
username='Username'
password='Password'
client = FiinSession(username=username, password=password).login()

# Bước 2: Lấy danh sách cổ phiếu trong VNIndex
tickers = client.TickerList(ticker="VNINDEX")

# Bước 3: Lấy dữ liệu lịch sử 60 ngày
event = client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=["close", "volume"],
    adjusted=True,
    by="1d",
    period=60,
    lasted=True
)
data = event.get_data()

# In ra latest timestamp
latest_timestamp = data["timestamp"].max()
print(f"=== DỮ LIỆU MỚI NHẤT TỚI NGÀY: {latest_timestamp} ===\n")

# Bước 4: Tính SMA20, SMA50 và lọc tín hiệu
fi = client.FiinIndicator()
cut_down, cut_up, above_ma50_falling, below_ma50_rising = [], [], [], []

for ticker in tickers:
    df = data[data['ticker'] == ticker].copy()
    df.sort_values("timestamp", inplace=True)
    df['sma_20'] = fi.sma(df['close'], window=20)
    df['sma_50'] = fi.sma(df['close'], window=50)

    if len(df) < 51:
        continue

    prev_close = df['close'].iloc[-2]
    curr_close = df['close'].iloc[-1]
    prev_sma20 = df['sma_20'].iloc[-2]
    curr_sma20 = df['sma_20'].iloc[-1]
    curr_sma50 = df['sma_50'].iloc[-1]
    volume = df['volume'].iloc[-1]

    if volume < 100_000:
        continue

    # Điều kiện cắt SMA20
    cut_down_condition = (prev_close > prev_sma20 and curr_close < curr_sma20 and
                          (curr_sma20 - curr_close) / curr_sma20 >= 0.005)
    cut_up_condition = (prev_close < prev_sma20 and curr_close > curr_sma20 and
                        (curr_close - curr_sma20) / curr_sma20 >= 0.005)

    if cut_down_condition:
        cut_down.append((ticker, volume))
    elif cut_up_condition:
        cut_up.append((ticker, volume))

    # Điều kiện giá > SMA50 nhưng đang giảm và cách SMA50 < 2%
    if curr_close > curr_sma50 and curr_close < prev_close and \
       abs(curr_close - curr_sma50) / curr_sma50 < 0.02:
        above_ma50_falling.append((ticker, curr_close, curr_sma50))

    # Điều kiện giá < SMA50 nhưng đang tăng và cách SMA50 < 2%
    if curr_close < curr_sma50 and curr_close > prev_close and \
       abs(curr_close - curr_sma50) / curr_sma50 < 0.02:
        below_ma50_rising.append((ticker, curr_close, curr_sma50))

# Bước 5: Sắp xếp theo volume
cut_down_sorted = sorted(cut_down, key=lambda x: x[1], reverse=True)
cut_up_sorted = sorted(cut_up, key=lambda x: x[1], reverse=True)

# Bước 6: In kết quả
print("=== CỔ PHIẾU CẮT XUỐNG SMA20 (>0.5%) VỚI VOLUME > 100K ===")
print(f"Tổng cộng: {len(cut_down_sorted)} mã")
for ticker, vol in cut_down_sorted:
    print(f"{ticker}: {vol:,}")

print("\n=== CỔ PHIẾU CẮT LÊN SMA20 (>0.5%) VỚI VOLUME > 100K ===")
print(f"Tổng cộng: {len(cut_up_sorted)} mã")
for ticker, vol in cut_up_sorted:
    print(f"{ticker}: {vol:,}")

print("\n=== CỔ PHIẾU GIÁ > SMA50, ĐANG GIẢM VÀ CÁCH MA50 <2% ===")
print(f"Tổng cộng: {len(above_ma50_falling)} mã")
for ticker, price, sma50 in above_ma50_falling:
    print(f"{ticker}: Close={price:.2f}, SMA50={sma50:.2f}, Chênh lệch={(price-sma50)/sma50*100:.2f}%")

print("\n=== CỔ PHIẾU GIÁ < SMA50, ĐANG TĂNG VÀ CÁCH MA50 <2% ===")
print(f"Tổng cộng: {len(below_ma50_rising)} mã")
for ticker, price, sma50 in below_ma50_rising:
    print(f"{ticker}: Close={price:.2f}, SMA50={sma50:.2f}, Chênh lệch={(price-sma50)/sma50*100:.2f}%")
```

## 5. Thống kê giá trị điều chỉnh khi thị trường tăng nóng

```python
import pandas as pd
import numpy as np
from FiinQuantX import FiinSession

# =========================
# 1) Đăng nhập & tham số
# =========================
username='username@fiingroup.vn',
password='password'
client = FiinSession(username=username, password=password).login()   # BẮT BUỘC phải login

# ========= 2) Tham số =========
ticker         = "VNINDEX"
from_date      = "2000-01-01"
timeframe      = "1d"
zigzag_pct     = 5.0     # ngưỡng ZigZag (% đảo chiều)
min_pump_pct   = 30.0    # ngưỡng tăng mạnh tối thiểu (%)

# ========= 3) Lấy dữ liệu =========
ev = client.Fetch_Trading_Data(
    realtime=False,
    tickers=ticker,
    fields=['close'],
    adjusted=True,
    by=timeframe,
    from_date=from_date
)
df = pd.DataFrame(ev.get_data())

# Chuẩn hóa thời gian (timestamp có thể là chuỗi)
df['time'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.sort_values('time').dropna(subset=['time', 'close']).reset_index(drop=True)
prices = df['close'].astype(float).values

# ========= 4) Hàm ZigZag vững chắc =========
def zigzag_points_by_pct(price_array: np.ndarray, pct: float):
    """Trả về danh sách pivot: [(idx, price, 'low'/'high'), ...]"""
    if price_array.size == 0:
        return []

    pivots = []
    # Khởi tạo: coi điểm đầu là cả đỉnh & đáy
    last_pivot_idx = 0
    last_pivot_val = price_array[0]
    trend = None  # None/'up'/'down'

    # Tìm swing đầu tiên vượt pct
    for i in range(1, len(price_array)):
        chg = (price_array[i] / last_pivot_val - 1.0) * 100.0
        if trend is None:
            if chg >= pct:
                pivots.append((last_pivot_idx, last_pivot_val, 'low'))
                last_pivot_idx, last_pivot_val = i, price_array[i]
                pivots.append((last_pivot_idx, last_pivot_val, 'high'))
                trend = 'up'
            elif chg <= -pct:
                pivots.append((last_pivot_idx, last_pivot_val, 'high'))
                last_pivot_idx, last_pivot_val = i, price_array[i]
                pivots.append((last_pivot_idx, last_pivot_val, 'low'))
                trend = 'down'
            else:
                # chưa đủ biên độ để xác lập trend
                if price_array[i] > last_pivot_val:
                    last_pivot_idx, last_pivot_val = i, price_array[i]  # dồn làm đỉnh tạm
                if price_array[i] < last_pivot_val:
                    last_pivot_idx, last_pivot_val = i, price_array[i]  # dồn làm đáy tạm
                continue
        else:
            if trend == 'up':
                # cập nhật đỉnh trong xu hướng lên
                if price_array[i] > last_pivot_val:
                    last_pivot_idx, last_pivot_val = i, price_array[i]
                    # cập nhật pivot 'high' cuối danh sách
                    if pivots and pivots[-1][2] == 'high':
                        pivots[-1] = (last_pivot_idx, last_pivot_val, 'high')
                # kiểm tra đảo chiều đủ pct
                drawdown = (price_array[i] / last_pivot_val - 1.0) * 100.0
                if drawdown <= -pct:
                    # chốt đỉnh
                    # (đỉnh đã là pivots[-1])
                    # bắt đầu xu hướng giảm: ghi đáy mới
                    last_pivot_idx, last_pivot_val = i, price_array[i]
                    pivots.append((last_pivot_idx, last_pivot_val, 'low'))
                    trend = 'down'
            else:  # trend == 'down'
                # cập nhật đáy trong xu hướng xuống
                if price_array[i] < last_pivot_val:
                    last_pivot_idx, last_pivot_val = i, price_array[i]
                    # cập nhật pivot 'low' cuối danh sách
                    if pivots and pivots[-1][2] == 'low':
                        pivots[-1] = (last_pivot_idx, last_pivot_val, 'low')
                # kiểm tra đảo chiều đủ pct
                rebound = (price_array[i] / last_pivot_val - 1.0) * 100.0
                if rebound >= pct:
                    # chốt đáy
                    # (đáy đã là pivots[-1])
                    # bắt đầu xu hướng lên: ghi đỉnh mới
                    last_pivot_idx, last_pivot_val = i, price_array[i]
                    pivots.append((last_pivot_idx, last_pivot_val, 'high'))
                    trend = 'up'

    # Lọc trùng chỉ số
    cleaned = []
    seen = set()
    for idx, val, typ in pivots:
        if idx not in seen:
            cleaned.append((idx, val, typ))
            seen.add(idx)
    return cleaned

pivots = zigzag_points_by_pct(prices, pct=zigzag_pct)

# ========= 5) Tạo bảng sự kiện: low -> high (tăng), rồi high -> low (chỉnh) =========
events = []
for i in range(len(pivots) - 2):
    i0, p0, t0 = pivots[i]
    i1, p1, t1 = pivots[i+1]
    i2, p2, t2 = pivots[i+2]
    if t0 == 'low' and t1 == 'high' and t2 == 'low':
        inc_pct = (p1 / p0 - 1.0) * 100.0
        if inc_pct >= min_pump_pct:
            corr_pct = (p2 / p1 - 1.0) * 100.0  # âm là giảm
            events.append({
                "start": df.loc[i0, 'time'],
                "peak":  df.loc[i1, 'time'],
                "end":   df.loc[i2, 'time'],
                "increase_%": round(inc_pct, 2),
                "correction_%": round(corr_pct, 2),
                "days": int((df.loc[i2, 'time'] - df.loc[i1, 'time']).days)
            })

# DataFrame kết quả (tạo cột dù trống để tránh KeyError)
result_cols = ["start", "peak", "end", "increase_%", "correction_%", "days"]
result = pd.DataFrame(events, columns=result_cols).sort_values('peak')

# ========= 6) Thống kê tổng hợp an toàn =========
def safe_stats(rdf: pd.DataFrame):
    if rdf.empty:
        return {
            "Số nhịp tăng >30% quan sát": 0,
            "Mức chỉnh TB (%)": np.nan,
            "Median (%)": np.nan,
            "Mức chỉnh lớn nhất (%)": np.nan,
            "Mức chỉnh nhỏ nhất (%)": np.nan,
            "Số ngày chỉnh TB": np.nan
        }
    return {
        "Số nhịp tăng >30% quan sát": int(len(rdf)),
        "Mức chỉnh TB (%)": round(rdf['correction_%'].mean(), 2),
        "Median (%)": round(rdf['correction_%'].median(), 2),
        "Mức chỉnh lớn nhất (%)": round(rdf['correction_%'].min(), 2),
        "Mức chỉnh nhỏ nhất (%)": round(rdf['correction_%'].max(), 2),
        "Số ngày chỉnh TB": round(rdf['days'].mean(), 1)
    }

summary = safe_stats(result)

# ========= 7) In kết quả =========
print("\n=== BẢNG SỰ KIỆN (VNINDEX) — tăng > %.1f%% rồi chỉnh theo ZigZag %.1f%% ===" % (min_pump_pct, zigzag_pct))
print(result.to_string(index=False))

print("\n=== THỐNG KÊ TỔNG HỢP (VNINDEX) ===")
for k, v in summary.items():
    print(f"{k}: {v}")

# ========= 8) Top 10 nhịp chỉnh mạnh nhất =========
if not result.empty:
    top10 = result.sort_values('correction_%').head(10)  # correction_% âm -> càng nhỏ càng giảm mạnh
    print("\n=== TOP 10 NHỊP CHỈNH MẠNH NHẤT ===")
    print(top10.to_string(index=False))

```
