# Danh sách dữ liệu hiện có

FiinQuant cung cấp đầy đủ các loại dữ liệu tài chính cho các nhà đầu tư, nhà phân tích và lập trình viên. Dưới đây là danh sách chi tiết các dữ liệu có sẵn.

## Tóm tắt các loại dữ liệu

| Nhóm dữ liệu             | Chi tiết                                                                                                        | Tình trạng                                                                  |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| **Giá & Khối lượng**     | OHLCV (Open - High - Low - Close - Volume), dữ liệu realtime & lịch sử.                                         | EOD<br/>Tick by Tick (Websocket)<br/>Intraday (1' 5' 15' 1h 4h)             |
| **Sổ lệnh (Order Book)** | Dữ liệu 3/10 mức giá mua – bán, volume bid/ask.                                                                 | Tick by Tick (Websocket)                                                    |
| **Dòng tiền chủ động**   | Mua chủ động/Bán chủ động                                                                                       | EOD<br/>Tick by Tick (Websocket)<br/>Intraday (1' 5' 15' 1h 4h)             |
| **Giao dịch khối ngoại** | Mua bán ròng theo từng mã                                                                                       | EOD<br/>Tick by Tick (Websocket)<br/>Intraday (1' 5' 15' 1h 4h)             |
| **Chỉ số tái cân bằng**  | Danh sánh mã theo rổ chỉ số. Chỉ số Freeloat, Outstanding Share, Marketcap Limit đối với các mã trong rổ chỉ số | EOD                                                                         |
| **Bộ chỉ số PTKT**       | Hơn 200 chỉ báo kỹ thuật                                                                                         | EOD<br/>Tick by Tick (Websocket)<br/>Intraday (1' 5' 15' 1h 4h)             |

## Chi tiết từng loại dữ liệu

### 1. Dữ liệu Giá & Khối lượng (OHLCV)

**Định nghĩa:**
- **O (Open)**: Giá mở cửa
- **H (High)**: Giá cao nhất
- **L (Low)**: Giá thấp nhất
- **C (Close)**: Giá đóng cửa
- **V (Volume)**: Khối lượng giao dịch

**Tính sẵn có:**
- ✅ Dữ liệu lịch sử (EOD - End of Day)
- ✅ Dữ liệu realtime (Tick by Tick qua Websocket)
- ✅ Dữ liệu Intraday: 1', 5', 15', 1h, 4h

**Hàm sử dụng:**
```python
# Dữ liệu lịch sử
client.get_historical_data(symbol, from_date, to_date, resolution)

# Dữ liệu realtime
client.get_realtime_data(symbol)

# Nối dữ liệu lịch sử và realtime
client.merge_historical_realtime(symbol, from_date, resolution)
```

### 2. Dữ liệu Sổ lệnh (Order Book)

**Thông tin:**
- Dữ liệu 3 mức giá mua - bán
- Dữ liệu 10 mức giá mua - bán (nếu có)
- Volume bid/ask ở từng mức

**Tính sẵn có:**
- ✅ Realtime qua Websocket (Tick by Tick)

**Mục đích sử dụng:**
- Phân tích độ sâu thị trường (Market Depth)
- Phát hiện áp lực mua/bán
- Xác định mức hỗ trợ và kháng cự

### 3. Dữ liệu Dòng tiền chủ động

**Loại dữ liệu:**
- Mua chủ động (Aggressive Buy)
- Bán chủ động (Aggressive Sell)

**Tính sẵn có:**
- ✅ Dữ liệu lịch sử (EOD)
- ✅ Dữ liệu realtime (Tick by Tick)
- ✅ Dữ liệu Intraday: 1', 5', 15', 1h, 4h

**Ứng dụng:**
- Xác định áp lực mua/bán của các nhà đầu tư lớn
- Dự báo xu hướng giá ngắn hạn

### 4. Dữ liệu Giao dịch khối ngoại (NĐTNN)

**Thông tin:**
- Mua bán ròng của nhà đầu tư nước ngoài
- Theo từng mã chứng khoán
- Cập nhật realtime trong phiên giao dịch

**Tính sẵn có:**
- ✅ Dữ liệu lịch sử (EOD)
- ✅ Dữ liệu realtime (Tick by Tick)
- ✅ Dữ liệu Intraday: 1', 5', 15', 1h, 4h

**Mục đích:**
- Theo dõi hoạt động nhà đầu tư nước ngoài
- Phân tích khối ngoại
- Xác định xu hướng thị trường

### 5. Dữ liệu Chỉ số tái cân bằng

**Nội dung:**
- Danh sách các mã trong rổ chỉ số
- Chỉ số Freeloat (cổ phiếu tự do)
- Outstanding Share (cổ phiếu phát hành)
- Marketcap Limit (giới hạn vốn hóa)

**Tính sẵn có:**
- ✅ Dữ liệu EOD
- ✅ Cập nhật khi có thay đổi trong chỉ số

### 6. Bộ chỉ báo Phân tích kỹ thuật (TA)

**Số lượng chỉ báo:**
- Hơn 200 chỉ báo kỹ thuật

**Các loại chỉ báo:**

#### Trend Indicators (Chỉ báo xu hướng)
- SMA, EMA, DEMA, TEMA, WMA
- ADX, Ichimoku, Supertrend
- Trendlines

#### Momentum Indicators (Chỉ báo động lượng)
- RSI, MACD, Stochastic
- Momentum, ROC, KDJ
- CCI, Williams %R

#### Volatility Indicators (Chỉ báo biến động)
- Bollinger Bands
- ATR, Keltner Channels
- Donchian Channels
- Standard Deviation

#### Volume Indicators (Chỉ báo khối lượng)
- OBV (On-Balance Volume)
- MFI (Money Flow Index)
- VWAP, Volume Rate of Change
- Accumulation/Distribution

#### Money Flow Indicators
- Money Flow
- Chaikin Money Flow
- Klinger Oscillator

#### Price Level Indicators
- Support & Resistance
- Fibonacci Retracements
- Pivot Points
- Murray Math

#### Smart Money Concepts
- Order Block
- Fair Value Gap
- Liquidity Levels

**Tính sẵn có:**
- ✅ Dữ liệu lịch sử (EOD)
- ✅ Dữ liệu realtime (Tick by Tick)
- ✅ Dữ liệu Intraday: 1', 5', 15', 1h, 4h

## Hướng dẫn sử dụng

### Lấy danh sách các loại dữ liệu sẵn có

```python
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lấy danh sách mã chứng khoán
symbols = client.get_symbol_list()

# Lấy danh sách các loại dữ liệu
data_types = client.get_available_data_types()

print(data_types)
```

### Kiểm tra dữ liệu có sẵn cho một mã cụ thể

```python
# Kiểm tra dữ liệu lịch sử
symbol = 'HPG'
from_date = '2023-01-01'
to_date = '2024-01-01'

data = client.get_historical_data(symbol, from_date, to_date)
print(data.head())
```

## Ghi chú quan trọng

- ⚠️ Dữ liệu realtime chỉ cập nhật trong giờ giao dịch
- 📅 Dữ liệu lịch sử có thể truy cập từ ngày giao dịch đầu tiên của từng mã
- 🔄 Cập nhật liên tục với dữ liệu mới từ các sở giao dịch
- 💾 Tất cả dữ liệu được lưu trữ an toàn trên máy chủ FiinQuant

## Tài liệu liên quan

- [2. Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
- [3. Phân tích cơ bản & Định giá](/ham-va-cong-thuc/3.-phan-tich-co-ban-and-dinh-gia.md)
- [8. Danh sách chỉ số TA](/ham-va-cong-thuc/8.-danh-sach-chi-so-ta.md)
