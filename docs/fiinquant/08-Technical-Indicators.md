# Chỉ báo Kỹ thuật (Technical Indicators) - Danh sách & Công thức

## Phần 8: Danh sách Chỉ báo Kỹ thuật

FiinQuant cung cấp hơn 200 chỉ báo kỹ thuật cho phân tích và giao dịch.

## I. Chỉ báo Xu hướng (Trend Indicators)

### 1. SMA (Simple Moving Average - Trung bình động đơn giản)

**Công thức:**
```
SMA(n) = (Close₁ + Close₂ + ... + Closeₙ) / n
```

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lấy dữ liệu với SMA
df = client.get_technical_indicator(
    symbol='HPG',
    from_date='2024-01-01',
    to_date='2024-01-31',
    indicator='SMA',
    period=20  # 20 ngày
)

print(df[['close', 'SMA_20']])
```

**Ý nghĩa:**
- SMA(20) > Giá: Xu hướng tăng
- SMA(20) < Giá: Xu hướng giảm
- Giao cắt: Tín hiệu mua/bán

### 2. EMA (Exponential Moving Average - Trung bình động hàm mũ)

**Công thức:**
```
EMA = Close × Multiplier + EMA(trước) × (1 - Multiplier)
Multiplier = 2 / (n + 1)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    from_date='2024-01-01',
    to_date='2024-01-31',
    indicator='EMA',
    period=12
)

print(df[['close', 'EMA_12']])
```

**Ý nghĩa:**
- EMA nhạy hơn SMA
- Thích hợp cho giao dịch ngắn hạn

### 3. DEMA (Double Exponential Moving Average)

**Công thức:**
```
DEMA = 2 × EMA - EMA(EMA)
```

**Ưu điểm:**
- Giảm độ trễ
- Phản ứng nhanh hơn

### 4. TEMA (Triple Exponential Moving Average)

**Công thức:**
```
TEMA = 3 × EMA - 3 × EMA(EMA) + EMA(EMA(EMA))
```

### 5. ADX (Average Directional Index)

**Mô tả:** Đo lực mạnh của xu hướng

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='ADX',
    period=14
)

print(df[['ADX_14', 'PLUS_DI', 'MINUS_DI']])
```

**Diễn giải:**
- ADX > 25: Xu hướng mạnh
- ADX < 20: Xu hướng yếu
- PLUS_DI > MINUS_DI: Xu hướng tăng
- PLUS_DI < MINUS_DI: Xu hướng giảm

### 6. Ichimoku Cloud

**Thành phần:**
- Tenkan-sen (Conversion Line)
- Kijun-sen (Base Line)
- Senkou Span A (Leading Span A)
- Senkou Span B (Leading Span B)
- Chikou Span (Lagging Span)

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='ICHIMOKU'
)

print(df[['tenkan', 'kijun', 'senkou_a', 'senkou_b', 'chikou']])
```

### 7. Supertrend

**Mô tả:** Kết hợp ATR và HA để tìm xu hướng

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='SUPERTREND',
    period=10,
    multiplier=3
)

print(df[['supertrend', 'direction']])
```

## II. Chỉ báo Động lượng (Momentum Indicators)

### 1. RSI (Relative Strength Index)

**Công thức:**
```
RS = Avg(Up) / Avg(Down)
RSI = 100 - (100 / (1 + RS))
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='RSI',
    period=14
)

print(df[['close', 'RSI_14']])
```

**Diễn giải:**
- RSI > 70: Overbought (quá mua)
- RSI < 30: Oversold (quá bán)
- RSI = 50: Trung tính

### 2. MACD (Moving Average Convergence Divergence)

**Công thức:**
```
MACD = EMA(12) - EMA(26)
Signal = EMA(MACD, 9)
Histogram = MACD - Signal
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='MACD'
)

print(df[['MACD', 'MACD_Signal', 'MACD_Histogram']])
```

**Tín hiệu:**
- MACD cắt Signal từ dưới lên: Tín hiệu mua
- MACD cắt Signal từ trên xuống: Tín hiệu bán
- Histogram tăng: Momentum tăng

### 3. Stochastic Oscillator

**Công thức:**
```
%K = (Close - Low(14)) / (High(14) - Low(14)) × 100
%D = SMA(%K, 3)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='STOCHASTIC',
    period=14,
    smooth_k=3,
    smooth_d=3
)

print(df[['%K', '%D']])
```

**Diễn giải:**
- %K > 80: Overbought
- %K < 20: Oversold
- Giao cắt: Tín hiệu mua/bán

### 4. Momentum

**Công thức:**
```
Momentum = Close(t) - Close(t-n)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='MOMENTUM',
    period=10
)

print(df['Momentum_10'])
```

### 5. ROC (Rate of Change)

**Công thức:**
```
ROC = ((Close(t) - Close(t-n)) / Close(t-n)) × 100
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='ROC',
    period=12
)

print(df['ROC_12'])
```

### 6. CCI (Commodity Channel Index)

**Công thức:**
```
CCI = (Typical Price - SMA(TP, 20)) / (0.015 × Mean Deviation)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='CCI',
    period=20
)

print(df['CCI_20'])
```

**Diễn giải:**
- CCI > +100: Overbought
- CCI < -100: Oversold

### 7. Williams %R

**Công thức:**
```
%R = -(High(14) - Close) / (High(14) - Low(14)) × 100
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='WILLIAMS_R',
    period=14
)

print(df['Williams_%R'])
```

## III. Chỉ báo Biến động (Volatility Indicators)

### 1. Bollinger Bands

**Công thức:**
```
Middle Band = SMA(20)
Upper Band = SMA(20) + (2 × StdDev)
Lower Band = SMA(20) - (2 × StdDev)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='BOLLINGER_BANDS',
    period=20,
    dev=2
)

print(df[['BB_Upper', 'BB_Middle', 'BB_Lower']])
```

**Ý nghĩa:**
- Giá chạm Upper Band: Có thể bán
- Giá chạm Lower Band: Có thể mua
- Khoảng cách Bands tăng: Biến động tăng

### 2. ATR (Average True Range)

**Công thức:**
```
ATR = EMA(True Range, 14)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='ATR',
    period=14
)

print(df['ATR_14'])
```

**Ứng dụng:**
- Xác định Stop Loss
- Đo biến động thị trường

### 3. Keltner Channels

**Công thức:**
```
Middle = EMA(20)
Upper = EMA(20) + (2 × ATR(10))
Lower = EMA(20) - (2 × ATR(10))
```

### 4. Donchian Channels

**Công thức:**
```
Upper = Highest(High, 20)
Lower = Lowest(Low, 20)
```

## IV. Chỉ báo Khối lượng (Volume Indicators)

### 1. OBV (On-Balance Volume)

**Công thức:**
```
OBV = OBV(trước) + Volume (nếu Close > Close trước)
OBV = OBV(trước) - Volume (nếu Close < Close trước)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='OBV'
)

print(df[['volume', 'OBV']])
```

### 2. MFI (Money Flow Index)

**Công thức:**
```
Typical Price = (High + Low + Close) / 3
Money Flow = Typical Price × Volume
MFI = 100 - (100 / (1 + Positive Money Flow / Negative Money Flow))
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='MFI',
    period=14
)

print(df['MFI_14'])
```

**Diễn giải:**
- MFI > 80: Overbought
- MFI < 20: Oversold

### 3. VWAP (Volume Weighted Average Price)

**Công thức:**
```
VWAP = Σ(Typical Price × Volume) / Σ(Volume)
```

**Hàm sử dụng:**
```python
df = client.get_technical_indicator(
    symbol='HPG',
    indicator='VWAP'
)

print(df['VWAP'])
```

### 4. A/D (Accumulation/Distribution)

**Công thức:**
```
A/D = (Close - Open) / (High - Low) × Volume
Cumulative A/D = Σ A/D
```

## V. Chỉ báo Dòng tiền (Money Flow)

### 1. Chaikin Money Flow

**Công thức:**
```
CMF = Σ((Close - Low) - (High - Close)) / (High - Low) × Volume / 20 / (Average Volume)
```

### 2. Klinger Oscillator

**Mô tả:** Kết hợp khối lượng và giá để xác định xu hướng

## VI. Chỉ báo Mức giá (Price Level Indicators)

### 1. Support & Resistance (Hỗ trợ & Kháng cự)

**Hàm sử dụng:**
```python
df = client.get_support_resistance(
    symbol='HPG',
    lookback=20
)

print(df[['support', 'resistance']])
```

### 2. Fibonacci Retracements

**Mức Fibonacci chính:**
- 23.6%
- 38.2%
- 50%
- 61.8%
- 78.6%

**Hàm sử dụng:**
```python
fib_levels = client.get_fibonacci_retracement(
    symbol='HPG',
    high=100,
    low=50
)

print(fib_levels)
```

### 3. Pivot Points

**Công thức:**
```
Pivot = (High + Low + Close) / 3
Resistance 1 = (Pivot × 2) - Low
Support 1 = (Pivot × 2) - High
Resistance 2 = Pivot + (High - Low)
Support 2 = Pivot - (High - Low)
```

**Hàm sử dụng:**
```python
df = client.get_pivot_points(
    symbol='HPG'
)

print(df[['Pivot', 'R1', 'R2', 'S1', 'S2']])
```

## VII. Smart Money Concepts

### 1. Order Block

**Mô tả:** Vùng giá nơi khối lượng giao dịch lớn tập trung

**Hàm sử dụng:**
```python
df = client.get_order_blocks(
    symbol='HPG'
)

print(df[['block_high', 'block_low', 'strength']])
```

### 2. Fair Value Gap (FVG)

**Mô tả:** Khoảng cách giá không được lấp đầy, có khả năng test lại

**Hàm sử dụng:**
```python
df = client.get_fair_value_gaps(
    symbol='HPG'
)

print(df[['gap_high', 'gap_low', 'type']])
```

### 3. Liquidity Levels

**Mô tả:** Mức giá nơi có nhiều lệnh treo (High/Low tạo trước đó)

## Ví dụ Thực tế

### Chiến lược Golden Cross

```python
# Golden Cross: SMA(50) cắt SMA(200) từ dưới lên = Tín hiệu mua
df = client.get_technical_indicator(
    symbol='HPG',
    from_date='2023-01-01',
    to_date='2024-01-31',
    indicator=['SMA', 'EMA'],
    periods=[50, 200]
)

df['Signal'] = 0
df.loc[df['SMA_50'] > df['SMA_200'], 'Signal'] = 1  # Tăng
df.loc[df['SMA_50'] < df['SMA_200'], 'Signal'] = -1  # Giảm

print(df[['SMA_50', 'SMA_200', 'Signal']])
```

### Chiến lược RSI + MACD

```python
rsi = client.get_technical_indicator(symbol='HPG', indicator='RSI')
macd = client.get_technical_indicator(symbol='HPG', indicator='MACD')

# Mua khi: RSI < 30 và MACD cắt Signal từ dưới lên
# Bán khi: RSI > 70 và MACD cắt Signal từ trên xuống
```

## Tài liệu liên quan

- [2. Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
- [3. Phân tích cơ bản & Định giá](/ham-va-cong-thuc/3.-phan-tich-co-ban-and-dinh-gia.md)
