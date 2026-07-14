# Dữ liệu Giao dịch - Hàm và Công thức

## Phần 2: Dữ liệu giao dịch

### 2.1. Hàm dữ liệu Lịch sử (Historical Data)

**Mô tả:**
Lấy dữ liệu giá lịch sử (OHLCV) từng cổ phiếu từ ngày bắt đầu đến ngày kết thúc

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession
import pandas as pd

client = FiinSession(username='your_username', password='your_password').login()

# Lấy dữ liệu hàng ngày (EOD - End of Day)
df_daily = client.get_historical_data(
    symbol='HPG',
    from_date='2023-01-01',
    to_date='2024-01-31',
    resolution='1D'  # 1 ngày
)

print(df_daily.head())
# Kết quả:
#            open   high    low  close    volume
# date
# 2023-01-02  45.5   46.0   45.0   45.8  1500000
# 2023-01-03  45.8   46.5   45.5   46.2  2000000
```

**Tham số:**
- `symbol` (string): Mã cổ phiếu (ví dụ: 'HPG', 'VNM', 'ACB')
- `from_date` (string): Ngày bắt đầu (định dạng 'YYYY-MM-DD')
- `to_date` (string): Ngày kết thúc (định dạng 'YYYY-MM-DD')
- `resolution` (string): Khung thời gian:
  - `'1D'` - Hàng ngày
  - `'1W'` - Hàng tuần
  - `'1M'` - Hàng tháng

**Dữ liệu trả về:**
- `open`: Giá mở cửa
- `high`: Giá cao nhất
- `low`: Giá thấp nhất
- `close`: Giá đóng cửa
- `volume`: Khối lượng giao dịch

### 2.2. Dữ liệu Intraday (Dữ liệu trong ngày)

**Mô tả:**
Lấy dữ liệu giá theo các khung thời gian nhỏ hơn 1 ngày (1 phút, 5 phút, 15 phút, 1 giờ, 4 giờ)

**Hàm sử dụng:**
```python
# Dữ liệu theo phút (1-minute candles)
df_1m = client.get_intraday_data(
    symbol='HPG',
    date='2024-01-15',  # Ngày cụ thể
    resolution='1'      # 1 phút
)

# Dữ liệu 5 phút
df_5m = client.get_intraday_data(
    symbol='HPG',
    date='2024-01-15',
    resolution='5'      # 5 phút
)

# Dữ liệu 15 phút
df_15m = client.get_intraday_data(
    symbol='HPG',
    date='2024-01-15',
    resolution='15'     # 15 phút
)

# Dữ liệu 1 giờ
df_1h = client.get_intraday_data(
    symbol='HPG',
    date='2024-01-15',
    resolution='60'     # 1 giờ = 60 phút
)

# Dữ liệu 4 giờ
df_4h = client.get_intraday_data(
    symbol='HPG',
    from_date='2024-01-01',
    to_date='2024-01-31',
    resolution='240'    # 4 giờ = 240 phút
)

print(df_5m.head())
```

**Các resolution hỗ trợ:**
- `'1'` - 1 phút
- `'5'` - 5 phút
- `'15'` - 15 phút
- `'60'` - 1 giờ
- `'240'` - 4 giờ

**Tham số:**
- `symbol` (string): Mã cổ phiếu
- `date` hoặc `from_date/to_date` (string): Ngày hoặc khoảng ngày
- `resolution` (string): Khung thời gian

### 2.3. Hàm nối dữ liệu Realtime và Lịch sử

**Mô tả:**
Tự động nối dữ liệu lịch sử với dữ liệu realtime để có bộ dữ liệu hoàn chỉnh

**Hàm sử dụng:**
```python
# Hợp nhất lịch sử và realtime
df_merged = client.merge_historical_realtime(
    symbol='HPG',
    from_date='2024-01-01',
    resolution='1D'  # hoặc '1', '5', '15', '60', '240'
)

# Kết quả bao gồm:
# - Dữ liệu lịch sử đã đóng (closed data)
# - Dữ liệu realtime hiện tại (nếu trong giờ giao dịch)

print(df_merged.tail(10))  # 10 row cuối cùng (gồm realtime)
```

**Ưu điểm:**
- ✅ Tự động cập nhật với dữ liệu mới nhất
- ✅ Không cần xử lý thủ công
- ✅ Phù hợp cho phân tích realtime

### 2.4. Dữ liệu Realtime (Real-time Data)

**Mô tả:**
Lấy dữ liệu giá realtime cập nhật liên tục qua Websocket

**Hàm sử dụng - Phương pháp 1: REST API**
```python
# Lấy một lần snapshot realtime
price = client.get_last_price('HPG')
print(f"Giá hiện tại HPG: {price}")

# Lấy dữ liệu realtime chi tiết
realtime_data = client.get_realtime_quote('HPG')
print(f"Giá: {realtime_data['close']}")
print(f"Khối lượng: {realtime_data['volume']}")
print(f"Khối lượng mua: {realtime_data['bid_volume']}")
print(f"Khối lượng bán: {realtime_data['ask_volume']}")
```

**Hàm sử dụng - Phương pháp 2: Websocket (Stream)**
```python
# Kết nối Websocket để nhận dữ liệu realtime liên tục
def on_price_update(symbol, data):
    print(f"{symbol}: {data['close']}")

# Subscribe
client.subscribe_realtime('HPG', callback=on_price_update)

# Chạy stream
client.run_websocket()
```

**Dữ liệu trả về:**
- `close`: Giá đóng cửa hiện tại
- `volume`: Khối lượng
- `bid`: Giá mua
- `ask`: Giá bán
- `bid_volume`: Khối lượng mua
- `ask_volume`: Khối lượng bán
- `time`: Thời gian cập nhật

### 2.5. Dữ liệu Tick by Tick

**Mô tả:**
Lấy từng giao dịch cụ thể (từng tick) với chi tiết giá và khối lượng

**Hàm sử dụng:**
```python
# Lấy tick data lịch sử
ticks = client.get_tick_data(
    symbol='HPG',
    date='2024-01-15'  # Ngày cụ thể
)

print(ticks.head())
# Kết quả:
#    time  price  volume  buyer_id  seller_id  transaction_type
# 0  09:30  45.5  10000   123      456        1
# 1  09:31  45.6  5000    789      012        -1
```

**Dữ liệu trả về:**
- `time`: Thời gian giao dịch
- `price`: Giá giao dịch
- `volume`: Khối lượng giao dịch
- `buyer_id`: ID người mua
- `seller_id`: ID người bán
- `transaction_type`: Loại giao dịch (1: mua chủ động, -1: bán chủ động, 0: giống nhau)

## Hàm xử lý dữ liệu

### Lọc dữ liệu

```python
# Lọc dữ liệu trong khoảng ngày
df_filtered = df_daily[(df_daily.index >= '2023-06-01') & 
                       (df_daily.index <= '2023-12-31')]

# Lọc dữ liệu dựa trên khối lượng
df_high_volume = df_daily[df_daily['volume'] > 1000000]
```

### Tính toán các chỉ số

```python
# Tính lợi nhuận hàng ngày
df_daily['returns'] = df_daily['close'].pct_change()

# Tính độ dao động (volatility)
df_daily['volatility'] = df_daily['returns'].rolling(20).std()

# Tính trung bình động
df_daily['sma_20'] = df_daily['close'].rolling(20).mean()
```

## Ví dụ thực tế

### Phân tích so sánh giá

```python
symbols = ['HPG', 'VNM', 'ACB']

for symbol in symbols:
    df = client.get_historical_data(
        symbol=symbol,
        from_date='2024-01-01',
        to_date='2024-01-31',
        resolution='1D'
    )
    
    latest_price = df['close'].iloc[-1]
    highest_price = df['high'].max()
    lowest_price = df['low'].min()
    
    print(f"{symbol}:")
    print(f"  Giá hiện tại: {latest_price}")
    print(f"  Giá cao nhất: {highest_price}")
    print(f"  Giá thấp nhất: {lowest_price}")
```

## Ghi chú quan trọng

- ⚠️ Dữ liệu lịch sử chỉ được cập nhật vào cuối phiên giao dịch
- 🔄 Dữ liệu realtime chỉ có trong giờ giao dịch (09:00 - 15:00)
- 📊 Tick data có khối lượng lớn, hãy lọc nếu cần
- 💾 Lưu dữ liệu vào file CSV để tái sử dụng

## Tài liệu liên quan

- [1. Danh mục và Thông tin cơ bản](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban.md)
- [3. Phân tích cơ bản & Định giá](/ham-va-cong-thuc/3.-phan-tich-co-ban-and-dinh-gia.md)
- [8. Danh sách chỉ số TA](/ham-va-cong-thuc/8.-danh-sach-chi-so-ta.md)
