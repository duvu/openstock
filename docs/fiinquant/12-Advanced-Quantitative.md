# 12. Thống kê Thị trường & Định lượng

## 4. Thống kê thị trường

### Lấy dữ liệu về độ rộng thị trường

Độ rộng thị trường (Market Breadth) là chỉ báo đo lường số lượng cổ phiếu tăng/giảm trong một ngày giao dịch:

- **Số mã sàn** (Floor Count): Tổng số mã cổ phiếu giao dịch
- **Số mã trần** (Ceiling): Mã đạt giá trần trong phiên
- **Số mã tăng/giảm** (Gainers/Losers): Số mã tăng giá hoặc giảm giá
- **Tham chiếu** (References): Mã duy trì giá bằng phiên trước

### Công thức tính

- **Advance/Decline Ratio** = Gainers / Losers
- **Breadth Strength** = (Gainers - Losers) / Total

### Ứng dụng
- Xác định xu hướng thị trường chung
- Phát hiện phân kỳ (Divergence)
- Cảnh báo đảo chiều trendline

---

## 5. Định lượng & Phân tích nâng cao

### 5.1 Hiệu suất (Performance)

#### Annualize - Chuyển đổi lợi nhuận thành suất hàng năm

**Công thức:**
```
Annual Return = (1 + Period Return)^(365/Period) - 1
```

Ví dụ: Lợi nhuận 10% trong 100 ngày → Annualized Return = (1.10)^(365/100) - 1 = 45.3%

#### Max Drawdown - Mức sụt giảm tối đa

**Công thức:**
```
Max Drawdown = (Peak Price - Trough Price) / Peak Price
```

Ví dụ: Giá cao nhất 100,000đ, thấp nhất 70,000đ → Max Drawdown = (100,000-70,000)/100,000 = 30%

**Ý nghĩa:**
- Max Drawdown 30% = portfolio có thể mất 30% so với đỉnh cao nhất
- Dùng để đánh giá rủi ro tối đa

---

### 5.2 Rủi ro (Risk)

#### Volatility - Biến động giá

**Công thức (Annualized):**
```
Annual Volatility = Daily Volatility × √252
```

**Ý nghĩa:**
- Volatility 20% = giá dao động khoảng ±20% trong năm
- Volatility cao = rủi ro cao, cơ hội lợi nhuận cao
- Volatility thấp = rủi ro thấp, nhưng lợi nhuận có thể bị hạn chế

#### Beta - Rủi ro hệ thống

**Công thức:**
```
Beta = Cov(Stock Return, Market Return) / Var(Market Return)
```

**Giải thích:**
- Beta = 1: Cổ phiếu dao động cùng thị trường
- Beta > 1: Cổ phiếu biến động mạnh hơn thị trường (rủi ro cao)
- Beta < 1: Cổ phiếu ổn định hơn thị trường (rủi ro thấp)
- Beta = 0: Không tương quan với thị trường

---

### 5.3 Tương quan & So sánh

#### Correlation - Hệ số tương quan

**Công thức Pearson:**
```
r = Cov(X, Y) / (σX × σY)
```

**Giải thích:**
- r = 1: Tương quan dương hoàn hảo (cùng tăng/giảm)
- r = 0: Không tương quan
- r = -1: Tương quan âm hoàn hảo (một tăng, một giảm)

**Ứng dụng Diversification:**
- Kết hợp assets có r < 0.5 để giảm rủi ro
- Tìm cổ phiếu ngành khác nhau giảm tương quan danh mục

#### Similar Chart - Tìm cổ phiếu tương tự

- So sánh mô hình biểu đồ giữa các cổ phiếu
- Dùng để tìm stock có hình dạng giá giống nhau
- Giúp xác định đảo ngược xu hướng (Mean Reversion)

#### Seasonality - Mô hình theo thời vụ

**Các mô hình thường gặp:**
1. **January Effect**: Thị trường thường tăng vào đầu năm
2. **Sell in May**: Thị trường yếu từ tháng 5-10
3. **Holiday Effect**: Thị trường tăng trước các ngày lễ lớn
4. **End-of-Month Rally**: Tăng giá vào cuối tháng

---

## 6. Chiến lược & công cụ

### 6.1 Rebalance - Tái cân bằng danh mục

**Khái niệm:**
- Điều chỉnh tỷ trọng portfolio theo định kỳ hoặc khi có biến động thị trường
- Bán những cổ phiếu tăng nhiều (để tỷ trọng không lệch)
- Mua những cổ phiếu giảm (để duy trì tỷ trọng)

**Chiến lược:**
1. **Buy Low, Sell High**: Tự động thực hiện khi rebalance
2. **Calendar Rebalancing**: Mỗi tháng/quý/năm
3. **Threshold Rebalancing**: Khi tỷ trọng lệch >5%

**Code mẫu:**
```python
initial_weights = {'VCB': 0.3, 'HPG': 0.3, 'FPT': 0.4}
current_value = {'VCB': 50000, 'HPG': 55000, 'FPT': 40000}
total_value = 145000

# Tính tỷ trọng hiện tại
current_weights = {k: v/total_value for k,v in current_value.items()}

# Tính chênh lệch
for ticker in initial_weights:
    diff = initial_weights[ticker] - current_weights[ticker]
    if diff > 0:
        print(f"BUY {ticker}: {diff*100:.1f}%")
    else:
        print(f"SELL {ticker}: {abs(diff)*100:.1f}%")
```

### 6.2 Relative Rotation Graph (RRG) - Biểu đồ sức mạnh giá

**Khái niệm:**
- Hiển thị 4 góc phần tư: Leading, Weakening, Lagging, Improving
- Mỗi cổ phiếu là một điểm trên biểu đồ
- So sánh sức mạnh tương đối so với index

**Các vùng:**
- **Leading (Phía trước)**: Cổ phiếu tốt hơn, momentum cao
- **Weakening (Suy yếu)**: Vừa từ Leading, bắt đầu suy yếu
- **Lagging (Tụt hậu)**: Cổ phiếu yếu hơn, momentum thấp
- **Improving (Cải thiện)**: Bắt đầu phục hồi

---

## 7. Hàm Đặt Lệnh

### 7.1-7.2 Đăng nhập & Tài khoản

**Yêu cầu:**
- Tài khoản FiinQuant hợp lệ
- Quyền giao dịch được kích hoạt
- Broker API credentials

### 7.3 Thông tin gói vay

**Các loại nguồn tiền:**
- T0: Tiền sẵn có trong tài khoản
- T1: Tiền từ bán cổ phiếu hôm qua
- Margin: Vay từ sàn giao dịch
- Short: Đi bán không có

### 7.4 OrderBook

- Khởi tạo đối tượng để quản lý các lệnh
- Ghi dõi trạng thái từng lệnh (Pending, Filled, Cancelled)
- Tính toán PnL (Profit & Loss)

### 7.5-7.10 Các hàm giao dịch

**Loại lệnh:**
1. **Market Order**: Thực hiện ngay tại giá hiện tại
2. **Limit Order**: Chờ khi giá đạt mức chỉ định
3. **Stop Loss**: Chốt lỗ tự động khi giá giảm
4. **Take Profit**: Chốt lãi tự động khi giá tăng

**Quản lý vị thế:**
- Mở/đóng vị thế (Position)
- Tính Margin Requirement
- Theo dõi PnL thực time

---

## 8. Danh sách Chỉ số Kỹ thuật (TA) - 200+ chỉ báo

### Chỉ báo Xu hướng
- **SMA** (Simple Moving Average)
- **EMA** (Exponential Moving Average)
- **DEMA, TEMA** (Double/Triple EMA)
- **ADX** (Average Directional Index)
- **Ichimoku Kinky Hyo**
- **Supertrend**

### Chỉ báo Động lượng
- **RSI** (Relative Strength Index)
- **MACD** (Moving Average Convergence Divergence)
- **Stochastic** (Fast, Slow, Full)
- **KDJ** (Kama Derivative Jump)
- **CCI** (Commodity Channel Index)
- **Momentum**
- **ROC** (Rate of Change)

### Chỉ báo Biến động
- **Bollinger Bands**
- **ATR** (Average True Range)
- **Keltner Channels**
- **NATR** (Normalized ATR)

### Chỉ báo Khối lượng
- **OBV** (On-Balance Volume)
- **MFI** (Money Flow Index)
- **VWAP** (Volume Weighted Average Price)
- **A/D** (Accumulation/Distribution)
- **CMF** (Chaikin Money Flow)

### Smart Money Concepts
- **Order Block**: Vùng accumulation/distribution lớn
- **Fair Value Gap (FVG)**: Khoảng trống giá
- **Liquidity Level**: Mức giá tập trung khối lệnh
- **BUS/SD**: Dòng tiền chủ động

---

## 9. Mô hình Pattern - Phân tích kỹ thuật

### 9.1 Mô hình Biểu đồ
- **Breakout**: Phá vỡ vùng kháng cự/hỗ trợ
- **Head & Shoulders**: Hình vai ngoằn
- **Double Top/Bottom**: Đỉnh/đáy kép
- **Triangle**: Hình tam giác (Ascending, Descending, Symmetrical)
- **Wedge**: Hình nêm
- **Channel**: Kênh giá

### 9.2 Mô hình Nến (Candlestick)
- **Doji**: Mở & đóng giá bằng nhau
- **Hammer/Hanging Man**: Búa/treo cổ
- **Engulfing**: Nuốn chửng
- **Harami**: Bà mẹ bọc
- **Morning Star/Evening Star**: Sao mai/sao chiều
- **Three White Soldiers/Black Crows**: 3 lính trắng/quạ đen

---

## 10. Bộ lọc Cổ phiếu

**Các tiêu chí lọc:**
1. Giá & Khối lượng
2. Tỷ lệ định giá (P/E, P/B, P/S)
3. Tỷ lệ hiệu quả hoạt động (ROE, ROA)
4. Tỷ lệ tăng trưởng
5. Kỹ thuật: MA Crossover, RSI, MACD

**Output:** Danh sách cổ phiếu thỏa mãn điều kiện

---

## 11. Dữ liệu Hỗ trợ

### 11.1 Danh sách cổ phiếu theo index
- VN30, VN100, HNX, UPCOM
- Các thành phần, trọng số, chi tiết

### 11.2 Danh sách nhóm ngành ICB
- 4 cấp độ phân loại ngành
- Từ Dầu khí → Chi tiết từng ngành con

---

**Cập nhật: 2026-07-14**
