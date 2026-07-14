# Phân tích Cơ bản & Định giá - Hàm và Công thức

## Phần 3: Phân tích Cơ bản & Định giá

### 3.1. Dữ liệu Tài chính Cơ bản (Financial Data)

**Mô tả:**
Lấy dữ liệu tài chính từ báo cáo tài chính của công ty (báo cáo quý, báo cáo năm)

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lấy dữ liệu tài chính theo quý
quarterly_data = client.get_financial_data(
    symbol='HPG',
    report_type='quarterly'  # 'quarterly' hoặc 'annual'
)

# Lấy dữ liệu tài chính theo năm
annual_data = client.get_financial_data(
    symbol='HPG',
    report_type='annual'
)

print(quarterly_data[['revenue', 'profit', 'eps', 'pe_ratio']])
```

**Chỉ số tài chính (Financial Metrics):**
- `revenue`: Doanh thu
- `gross_profit`: Lợi nhuận gộp
- `operating_profit`: Lợi nhuận hoạt động
- `net_profit`: Lợi nhuận ròng
- `eps`: Lợi nhuận trên cổ phiếu (Earnings Per Share)
- `book_value`: Giá trị sổ sách
- `book_value_per_share`: Giá trị sổ sách trên cổ phiếu

### 3.2. Tỷ lệ Định giá (Valuation Ratios)

**Mô tả:**
Các tỷ lệ để đánh giá mức độ rẻ/mắc của cổ phiếu so với giá trị nội tại

**Hàm sử dụng:**
```python
# Lấy tỷ lệ định giá
valuation = client.get_valuation_ratios('HPG')

print(f"P/E Ratio: {valuation['pe_ratio']}")
print(f"P/B Ratio: {valuation['pb_ratio']}")
print(f"P/S Ratio: {valuation['ps_ratio']}")
print(f"Dividend Yield: {valuation['dividend_yield']}")
```

**Các tỷ lệ chính:**

#### 1. P/E Ratio (Price-to-Earnings Ratio)
```
P/E Ratio = Giá cổ phiếu / Lợi nhuận trên cổ phiếu (EPS)
```
- Ý nghĩa: Giá cổ phiếu bằng bao nhiêu lần lợi nhuận
- P/E thấp: Cổ phiếu rẻ
- P/E cao: Cổ phiếu mắc

**Mã P/E ngành trên VN30:**
| Ngành | Trung bình P/E |
|-------|---|
| Ngân hàng | 10-15x |
| Bất động sản | 8-12x |
| Công nghệ | 20-30x |
| Bán lẻ | 12-18x |

#### 2. P/B Ratio (Price-to-Book Ratio)
```
P/B Ratio = Giá cổ phiếu / Giá trị sổ sách trên cổ phiếu
```
- Ý nghĩa: Giá cổ phiếu bằng bao nhiêu lần giá trị tài sản
- P/B < 1: Cổ phiếu giao dịch dưới giá trị tài sản

#### 3. P/S Ratio (Price-to-Sales Ratio)
```
P/S Ratio = Giá cổ phiếu / Doanh thu trên cổ phiếu
```
- Ý nghĩa: Giá cổ phiếu bằng bao nhiêu lần doanh thu
- Ít bị ảnh hưởng bởi chính sách kế toán

#### 4. EV/EBITDA (Enterprise Value / EBITDA)
```
EV/EBITDA = Giá trị doanh nghiệp / EBITDA
```
- EBITDA = Lợi nhuận trước lãi vay, thuế, khấu hao
- Dùng để so sánh các công ty có nợ khác nhau

#### 5. Dividend Yield
```
Dividend Yield = Cổ tức năm / Giá cổ phiếu × 100%
```
- Ý nghĩa: Mức thoả thuận cổ tức hàng năm
- Thường từ 2-5% ở các cổ phiếu chia cổ tức

### 3.3. Tỷ lệ Hiệu quả Hoạt động (Profitability Ratios)

**Hàm sử dụng:**
```python
# Lấy tỷ lệ hiệu quả hoạt động
profitability = client.get_profitability_ratios('HPG')

print(f"ROE: {profitability['roe']}%")          # Return on Equity
print(f"ROA: {profitability['roa']}%")          # Return on Assets
print(f"Net Margin: {profitability['net_margin']}%")  # Biên lợi nhuận ròng
print(f"Gross Margin: {profitability['gross_margin']}%")  # Biên lợi nhuận gộp
```

**Các tỷ lệ chính:**

#### 1. ROE (Return on Equity - Lợi nhuận trên Vốn chủ sở hữu)
```
ROE = Lợi nhuận ròng / Vốn chủ sở hữu × 100%
```
- Ý nghĩa: Công ty sinh ra bao nhiêu lợi nhuận từ 1 VNĐ vốn
- Mức tốt: > 15%
- Mức rất tốt: > 20%

#### 2. ROA (Return on Assets - Lợi nhuận trên Tổng tài sản)
```
ROA = Lợi nhuận ròng / Tổng tài sản × 100%
```
- Ý nghĩa: Công ty sử dụng tài sản có hiệu quả như thế nào
- Mức tốt: > 5-10%

#### 3. Profit Margin (Biên lợi nhuận)
```
Gross Margin = Lợi nhuận gộp / Doanh thu × 100%
Operating Margin = Lợi nhuận hoạt động / Doanh thu × 100%
Net Margin = Lợi nhuận ròng / Doanh thu × 100%
```
- Ý nghĩa: Bao nhiêu % doanh thu trở thành lợi nhuận
- Margin cao: Hiệu quả hoạt động tốt

### 3.4. Tỷ lệ Thanh khoản & Solvency (Liquidity & Solvency Ratios)

**Hàm sử dụng:**
```python
# Lấy tỷ lệ thanh khoản
liquidity = client.get_liquidity_ratios('HPG')

print(f"Current Ratio: {liquidity['current_ratio']}")    # Tỷ lệ thanh khoản hiện tại
print(f"Quick Ratio: {liquidity['quick_ratio']}")        # Tỷ lệ thanh khoản nhanh
print(f"Debt Ratio: {liquidity['debt_ratio']}%")         # Tỷ lệ nợ
print(f"Debt-to-Equity: {liquidity['debt_to_equity']}")  # Tỷ lệ nợ trên vốn
```

**Các tỷ lệ chính:**

#### 1. Current Ratio (Tỷ lệ thanh khoản hiện tại)
```
Current Ratio = Tài sản hiện tại / Nợ hiện tại
```
- Ý nghĩa: Công ty có khả năng thanh toán các khoản nợ ngắn hạn
- Mức bình thường: 1.5 - 3.0
- Mức tốt: 2.0 - 2.5

#### 2. Quick Ratio (Tỷ lệ thanh khoản nhanh)
```
Quick Ratio = (Tài sản hiện tại - Hàng tồn kho) / Nợ hiện tại
```
- Ý nghĩa: Công ty có thể thanh toán nợ mà không cần bán hàng tồn kho
- Mức tốt: > 1.0

#### 3. Debt Ratio (Tỷ lệ nợ)
```
Debt Ratio = Tổng nợ / Tổng tài sản × 100%
```
- Ý nghĩa: Bao nhiêu % tài sản được tài trợ bằng nợ
- Mức an toàn: < 50%

#### 4. Debt-to-Equity Ratio
```
D/E = Tổng nợ / Vốn chủ sở hữu
```
- Ý nghĩa: Tỷ lệ giữa nợ và vốn chủ sở hữu
- Mức bình thường: 0.5 - 1.5

### 3.5. Tỷ lệ Tăng trưởng (Growth Ratios)

**Hàm sử dụng:**
```python
# Lấy tỷ lệ tăng trưởng
growth = client.get_growth_ratios('HPG', periods=5)  # 5 năm

print(f"Revenue Growth: {growth['revenue_growth']}%")
print(f"Profit Growth: {growth['profit_growth']}%")
print(f"EPS Growth: {growth['eps_growth']}%")
```

**Các chỉ số chính:**

#### 1. Revenue Growth (Tăng trưởng doanh thu)
```
Revenue Growth = (Doanh thu năm hiện tại - Doanh thu năm trước) / Doanh thu năm trước × 100%
```

#### 2. Profit Growth (Tăng trưởng lợi nhuận)
```
Profit Growth = (Lợi nhuận năm hiện tại - Lợi nhuận năm trước) / Lợi nhuận năm trước × 100%
```

#### 3. CAGR (Compound Annual Growth Rate)
```
CAGR = (Giá trị cuối / Giá trị đầu)^(1/n) - 1 × 100%
```
- n = số năm

### 3.6. Cổ tức & Thoả thuận (Dividend & Payout)

**Hàm sử dụng:**
```python
# Lấy thông tin cổ tức
dividend = client.get_dividend_info('HPG')

print(f"Dividend per share: {dividend['dps']}")         # Cổ tức trên cổ phiếu
print(f"Dividend yield: {dividend['yield']}%")          # Lợi suất cổ tức
print(f"Payout ratio: {dividend['payout_ratio']}%")     # Tỷ lệ trả cổ tức
print(f"Ex-dividend date: {dividend['ex_date']}")       # Ngày chốt quyền
```

**Các chỉ số chính:**

#### 1. Dividend Per Share (DPS)
```
DPS = Tổng cổ tức / Số lượng cổ phiếu
```

#### 2. Dividend Yield
```
Dividend Yield = DPS / Giá cổ phiếu × 100%
```

#### 3. Payout Ratio (Tỷ lệ trả cổ tức)
```
Payout Ratio = Cổ tức / Lợi nhuận ròng × 100%
```
- Ý nghĩa: Bao nhiêu % lợi nhuận được chia cho cổ đông
- Mức bình thường: 30-70%

## Ví dụ Phân tích Thực tế

### So sánh Định giá giữa các công ty

```python
symbols = ['HPG', 'VNM', 'ACB']

comparison = {}
for symbol in symbols:
    valuation = client.get_valuation_ratios(symbol)
    profitability = client.get_profitability_ratios(symbol)
    
    comparison[symbol] = {
        'PE': valuation['pe_ratio'],
        'PB': valuation['pb_ratio'],
        'ROE': profitability['roe'],
        'Net Margin': profitability['net_margin']
    }

import pandas as pd
df = pd.DataFrame(comparison).T
print(df)
```

### Tìm cổ phiếu rẻ (Value Investing)

```python
# Tìm cổ phiếu có P/E thấp và ROE cao
symbols = client.get_symbols_by_index('VN30')

good_stocks = []
for symbol in symbols:
    valuation = client.get_valuation_ratios(symbol)
    profitability = client.get_profitability_ratios(symbol)
    
    if valuation['pe_ratio'] < 15 and profitability['roe'] > 15:
        good_stocks.append({
            'Symbol': symbol,
            'PE': valuation['pe_ratio'],
            'ROE': profitability['roe']
        })

df = pd.DataFrame(good_stocks)
print(df.sort_values('PE'))
```

## Tài liệu liên quan

- [1. Danh mục và Thông tin cơ bản](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban.md)
- [2. Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
- [8. Danh sách chỉ số TA](/ham-va-cong-thuc/8.-danh-sach-chi-so-ta.md)
