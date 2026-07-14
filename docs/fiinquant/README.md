# FiinQuant Documentation - Danh mục Chi tiết

Tài liệu hoàn chỉnh về FiinQuant - Thư viện lấy dữ liệu và phân tích thị trường chứng khoán Việt Nam.

---

## 📚 Danh mục Tài liệu

### I. GIỚI THIỆU & CHUẨN BỊ

#### [00. FiinQuant - Tổng quan](00-README.md)
- ✅ FiinQuant là gì
- ✅ Các tính năng chính
- ✅ Thông tin liên hệ

#### [01. Cài đặt & Chuẩn bị](01-Installation.md)
- ✅ Cài đặt Python từ Python.org
- ✅ Cài đặt FiinQuantX qua pip
- ✅ Xác minh cài đặt thành công

#### [02. Đăng nhập Tài khoản](02-Login.md)
- ✅ Cách đăng nhập với FiinSession
- ✅ Xử lý lỗi đăng nhập
- ✅ Quản lý phiên làm việc

#### [03. Danh sách Phiên bản](03-Versions.md)
- ✅ Version hiện tại (v0.1.60)
- ✅ Lịch sử các phiên bản
- ✅ Hướng dẫn cập nhật

#### [04. Danh sách Dữ liệu Hiện có](04-Available-Data.md)
- ✅ Giá & Khối lượng (OHLCV)
- ✅ Sổ lệnh (Order Book)
- ✅ Dòng tiền chủ động
- ✅ Giao dịch khối ngoại (NĐTNN)
- ✅ Chỉ báo kỹ thuật (200+ chỉ báo)

---

### II. HÀM & CÔNG THỨC

#### [05. Danh mục & Thông tin Cơ bản - Phần 1](05-Functions-Part1.md)
- ✅ Danh sách mã theo Index (VN30, VN100, HNX, UPCOM)
- ✅ Danh sách mã theo Ngành
- ✅ Danh sách mã theo Tỷ trọng
- ✅ Vốn hóa thị trường (Market Cap)
- ✅ Room NĐTNN (Foreign Investor Room)
- ✅ Freefloat & Giá trần/sàn
- ✅ Giao dịch theo Nhà đầu tư

#### [06. Dữ liệu Giao dịch - Phần 2](06-Functions-Part2.md)
- ✅ Dữ liệu Lịch sử (Historical Data)
- ✅ Dữ liệu Intraday (1', 5', 15', 1h, 4h)
- ✅ Nối dữ liệu Realtime + Lịch sử
- ✅ Dữ liệu Realtime (Real-time Quote)
- ✅ Dữ liệu Tick by Tick
- ✅ Xử lý & Lọc dữ liệu

#### [07. Phân tích Cơ bản & Định giá - Phần 3](07-Functions-Part3.md)
- ✅ Dữ liệu Tài chính (Revenue, Profit, EPS)
- ✅ Tỷ lệ Định giá (P/E, P/B, P/S, EV/EBITDA)
- ✅ Tỷ lệ Hiệu quả Hoạt động (ROE, ROA, Margin)
- ✅ Tỷ lệ Thanh khoản & Solvency
- ✅ Tỷ lệ Tăng trưởng (CAGR, Growth Rate)
- ✅ Cổ tức & Thoả thuận (Dividend Yield, Payout Ratio)

#### [08. Chỉ báo Kỹ thuật - Danh sách Chi tiết](08-Technical-Indicators.md)
**Chỉ báo Xu hướng (Trend):**
- ✅ SMA, EMA, DEMA, TEMA
- ✅ ADX, Ichimoku, Supertrend

**Chỉ báo Động lượng (Momentum):**
- ✅ RSI, MACD, Stochastic, KDJ
- ✅ CCI, Williams %R, ROC, Momentum

**Chỉ báo Biến động (Volatility):**
- ✅ Bollinger Bands, ATR
- ✅ Keltner Channels, Donchian Channels

**Chỉ báo Khối lượng (Volume):**
- ✅ OBV, MFI, VWAP, A/D

**Khái niệm Smart Money:**
- ✅ Order Block, Fair Value Gap
- ✅ Liquidity Levels, Support & Resistance

#### [09. Bộ lọc Cổ phiếu (Stock Screener)](09-Stock-Screener.md)
- ✅ Lọc theo Giá & Khối lượng
- ✅ Lọc theo Tỷ lệ Định giá
- ✅ Lọc theo Lợi suất Cổ tức
- ✅ Lọc theo Hiệu quả Hoạt động
- ✅ Lọc theo Sức khỏe Tài chính
- ✅ Lọc theo Tăng trưởng
- ✅ Lọc theo Kỹ thuật & Ngành
- ✅ Kết hợp Nhiều tiêu chí

---

### III. ỨNG DỤNG THỰC TẾ

#### [10. Ứng dụng Thực tế - Lấy dữ liệu, Phân tích, Giao dịch](10-Practical-Applications.md)
1. **Lấy Dữ liệu Toàn bộ VN30**
2. **Tính Lợi nhuận & Rủi ro**
3. **Xây dựng Portfolio (Danh mục)**
   - Equally-Weighted
   - Market-Cap Weighted
4. **Phân tích Tương quan (Correlation)**
5. **Phân tích Động lực (Momentum)**
6. **Chiến lược Giao dịch Golden Cross**
7. **Chiến lược RSI + MACD**
8. **Tính toán Performance (Hiệu suất)**
9. **Quản lý Rủi ro (Risk Management)**
10. **Backtesting Chiến lược**

---

### IV. HƯỚNG DẪN LẬP TRÌNH PYTHON

#### [11. Python - Cấu trúc Dữ liệu & Thực hành Tốt nhất](11-Python-Best-Practices.md)
- ✅ DataFrame, Series, Dictionary, List
- ✅ Xử lý Dữ liệu với Pandas
- ✅ Lọc, Thêm cột, Tính toán Tổng hợp
- ✅ Kết hợp Dữ liệu từ nhiều nguồn
- ✅ Lưu & Đọc từ File (CSV, Excel, JSON)
- ✅ Xử lý Lỗi (Error Handling)
- ✅ Vòng lặp Hiệu quả & Vectorization
- ✅ Hàm Tái sử dụng
- ✅ Thực hành Tốt nhất:
  - Quản lý Phiên làm việc
  - Lưu Log
  - Cache Dữ liệu
  - Validation Dữ liệu

---

## 🎯 Hướng dẫn Sử dụng

### Bạn muốn làm gì?

#### 📊 **Lấy dữ liệu giá cổ phiếu?**
1. Đọc [01. Cài đặt](01-Installation.md)
2. Đọc [02. Đăng nhập](02-Login.md)
3. Đọc [06. Dữ liệu Giao dịch](06-Functions-Part2.md)

#### 📈 **Phân tích Cơ bản một cổ phiếu?**
1. Đọc [07. Phân tích Cơ bản & Định giá](07-Functions-Part3.md)
2. Ứng dụng [10. Ứng dụng Thực tế](10-Practical-Applications.md)

#### 🔍 **Phân tích Kỹ thuật?**
1. Đọc [08. Chỉ báo Kỹ thuật](08-Technical-Indicators.md)
2. Ứng dụng [10. Ứng dụng Thực tế](10-Practical-Applications.md) - Chiến lược Giao dịch

#### 🎣 **Tìm cổ phiếu thỏa mãn tiêu chí?**
1. Đọc [09. Bộ lọc Cổ phiếu](09-Stock-Screener.md)
2. Xem Ví dụ thực tế

#### 💼 **Xây dựng và Kiểm tra Chiến lược Giao dịch?**
1. Đọc [10. Ứng dụng Thực tế](10-Practical-Applications.md)
2. Xem các Chiến lược mẫu

#### 🐍 **Tìm hiểu Lập trình Python?**
1. Đọc [11. Python - Best Practices](11-Python-Best-Practices.md)
2. Xem Ví dụ Code

---

## 🚀 Bắt đầu Nhanh (Quick Start)

### 1. Cài đặt (5 phút)

```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

### 2. Đăng nhập (2 phút)

```python
from FiinQuantX import FiinSession

client = FiinSession(
    username='your_username',
    password='your_password'
).login()
```

### 3. Lấy dữ liệu (2 phút)

```python
# Lấy dữ liệu HPG
df = client.get_historical_data(
    symbol='HPG',
    from_date='2024-01-01',
    to_date='2024-01-31',
    resolution='1D'
)

print(df)
```

### 4. Phân tích (5 phút)

```python
# Tính SMA
df['SMA20'] = df['close'].rolling(20).mean()

# Tìm vùng bị bán quá mức (RSI < 30)
rsi = client.get_technical_indicator(
    symbol='HPG',
    indicator='RSI'
)

oversold = rsi[rsi['RSI_14'] < 30]
print(oversold)
```

---

## 📖 Danh sách Tỷ lệ Tài chính

| Tỷ lệ | Công thức | Ý nghĩa | Tốt | Rất tốt |
|-------|-----------|---------|-----|---------|
| P/E Ratio | Giá / EPS | Rẻ-Mắc | < 15 | < 10 |
| P/B Ratio | Giá / Giá trị sổ sách | So với tài sản | < 1.5 | < 1.0 |
| ROE | Lợi nhuận / Vốn | Hiệu quả | > 10% | > 15% |
| ROA | Lợi nhuận / Tài sản | Hiệu quả | > 5% | > 10% |
| Net Margin | Lợi nhuận / Doanh thu | Hiệu quả | > 5% | > 10% |
| Current Ratio | TL hiện tại / Nợ hiện tại | Thanh khoản | 1.5-3.0 | 2.0-2.5 |
| Debt Ratio | Nợ / Tài sản | Tài chính | < 50% | < 40% |
| Dividend Yield | DPS / Giá | Cổ tức | > 2% | > 3% |

---

## 🔗 Liên kết Ngoài

- **FiinQuant Official:** https://fiinquant.vn
- **Documentation:** https://docs.fiinquant.vn
- **PyPI Package:** https://pypi.org/fiinquantx
- **GitHub:** https://github.com/fiinquant

---

## 📝 Ghi chú Quan trọng

⚠️ **Yêu cầu Tài khoản:** Bạn cần tài khoản FiinQuant hợp lệ để sử dụng API

⏰ **Giữ Phiên Đăng nhập:** Session có thể hết hạn, kiểm tra trạng thái định kỳ

📊 **Dữ liệu Realtime:** Chỉ cập nhật trong giờ giao dịch (09:00-15:00)

💾 **Cache Dữ liệu:** Lưu dữ liệu lịch sử vào file để tránh request quá nhiều

🔄 **Rate Limit:** Không gửi quá nhiều request cùng một lúc

---

## 📞 Hỗ Trợ

Nếu gặp vấn đề:

1. Kiểm tra [03. Danh sách Phiên bản](03-Versions.md) - Đảm bảo bạn dùng version mới nhất
2. Kiểm tra [02. Đăng nhập](02-Login.md) - Kiểm tra tài khoản/mật khẩu
3. Xem [11. Python Best Practices](11-Python-Best-Practices.md) - Xử lý lỗi
4. Liên hệ FiinQuant qua https://fiinquant.vn/Home/Contact

---

**Cập nhật lần cuối:** 2024-01-31  
**Phiên bản:** v0.1.60  
**Ngôn ngữ:** Python 3.8+

Chúc bạn thành công với FiinQuant! 🎉
