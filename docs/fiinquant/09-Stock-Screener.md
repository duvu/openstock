# Bộ lọc Cổ phiếu - Hàm và Công thức

## Phần 10: Bộ lọc cổ phiếu (Stock Screener)

### Mô tả

Bộ lọc cổ phiếu cho phép bạn tìm kiếm cổ phiếu dựa trên nhiều tiêu chí khác nhau (giá, khối lượng, tỷ lệ tài chính, kỹ thuật).

### Hàm Lọc Cơ bản

#### 1. Lọc theo Giá & Khối lượng

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lọc cổ phiếu có giá từ 20 - 50 VNĐ
stocks = client.screen_stocks(
    filters={
        'price_min': 20,
        'price_max': 50,
        'volume_min': 500000  # Khối lượng tối thiểu 500k
    }
)

print(stocks[['symbol', 'price', 'volume']])
```

**Tham số:**
- `price_min`: Giá tối thiểu
- `price_max`: Giá tối đa
- `volume_min`: Khối lượng tối thiểu

#### 2. Lọc theo Tỷ lệ Định giá

**Hàm sử dụng:**
```python
# Lọc cổ phiếu có P/E < 15 (rẻ)
stocks = client.screen_stocks(
    filters={
        'pe_ratio_max': 15,
        'pb_ratio_min': 0.5,  # P/B > 0.5
        'pb_ratio_max': 1.5   # P/B < 1.5
    }
)

print(stocks[['symbol', 'pe_ratio', 'pb_ratio']])
```

**Tham số:**
- `pe_ratio_min` / `pe_ratio_max`: P/E Ratio
- `pb_ratio_min` / `pb_ratio_max`: P/B Ratio
- `ps_ratio_min` / `ps_ratio_max`: P/S Ratio

#### 3. Lọc theo Lợi suất Cổ tức

**Hàm sử dụng:**
```python
# Lọc cổ phiếu chia cổ tức cao (yield > 3%)
stocks = client.screen_stocks(
    filters={
        'dividend_yield_min': 3,
        'payout_ratio_max': 60  # Tỷ lệ trả < 60%
    }
)

print(stocks[['symbol', 'dividend_yield', 'dividend_per_share']])
```

**Tham số:**
- `dividend_yield_min` / `dividend_yield_max`: Lợi suất cổ tức
- `payout_ratio_min` / `payout_ratio_max`: Tỷ lệ trả cổ tức

#### 4. Lọc theo Hiệu quả Hoạt động

**Hàm sử dụng:**
```python
# Lọc cổ phiếu có ROE cao
stocks = client.screen_stocks(
    filters={
        'roe_min': 15,           # ROE > 15%
        'roa_min': 5,            # ROA > 5%
        'net_margin_min': 10     # Net Margin > 10%
    }
)

print(stocks[['symbol', 'roe', 'roa', 'net_margin']])
```

**Tham số:**
- `roe_min` / `roe_max`: Return on Equity
- `roa_min` / `roa_max`: Return on Assets
- `net_margin_min` / `net_margin_max`: Net Margin
- `gross_margin_min` / `gross_margin_max`: Gross Margin

#### 5. Lọc theo Sức khỏe Tài chính

**Hàm sử dụng:**
```python
# Lọc cổ phiếu có tài chính vững
stocks = client.screen_stocks(
    filters={
        'current_ratio_min': 1.5,    # Current Ratio > 1.5
        'debt_ratio_max': 40,         # Debt Ratio < 40%
        'debt_to_equity_max': 1       # D/E < 1
    }
)

print(stocks[['symbol', 'current_ratio', 'debt_ratio', 'debt_to_equity']])
```

**Tham số:**
- `current_ratio_min` / `current_ratio_max`: Tỷ lệ thanh khoản
- `quick_ratio_min` / `quick_ratio_max`: Tỷ lệ thanh khoản nhanh
- `debt_ratio_min` / `debt_ratio_max`: Tỷ lệ nợ
- `debt_to_equity_min` / `debt_to_equity_max`: Tỷ lệ D/E

#### 6. Lọc theo Tăng trưởng

**Hàm sử dụng:**
```python
# Lọc cổ phiếu có tăng trưởng tốt (năm)
stocks = client.screen_stocks(
    filters={
        'revenue_growth_min': 10,     # Doanh thu tăng > 10%
        'profit_growth_min': 10,      # Lợi nhuận tăng > 10%
        'eps_growth_min': 5           # EPS tăng > 5%
    }
)

print(stocks[['symbol', 'revenue_growth', 'profit_growth', 'eps_growth']])
```

**Tham số:**
- `revenue_growth_min` / `revenue_growth_max`: Tăng trưởng doanh thu
- `profit_growth_min` / `profit_growth_max`: Tăng trưởng lợi nhuận
- `eps_growth_min` / `eps_growth_max`: Tăng trưởng EPS

#### 7. Lọc theo Kỹ thuật

**Hàm sử dụng:**
```python
# Lọc cổ phiếu ở trên đường SMA(20)
stocks = client.screen_stocks(
    filters={
        'price_above_sma': 20,        # Giá > SMA(20)
        'rsi_min': 30,                # RSI > 30
        'rsi_max': 70,                # RSI < 70
        'macd_positive': True         # MACD dương
    }
)

print(stocks[['symbol', 'price', 'sma_20', 'rsi', 'macd']])
```

#### 8. Lọc theo Ngành

**Hàm sử dụng:**
```python
# Lọc cổ phiếu theo ngành
stocks = client.screen_stocks(
    filters={
        'sector': 'Technology',  # Ngành
        'industry': 'Software'   # Hạng mục
    }
)

print(stocks[['symbol', 'sector', 'industry']])
```

#### 9. Lọc theo Sàn Giao dịch

**Hàm sử dụng:**
```python
# Lọc cổ phiếu VN30
stocks = client.screen_stocks(
    filters={
        'index': 'VN30'  # VN30, VN100, HNX, UPCOM
    }
)

print(stocks[['symbol', 'exchange']])
```

### Kết hợp Nhiều Tiêu chí

**Ví dụ: Tìm cổ phiếu giá rẻ, ROE cao, chia cổ tức**

```python
# Value Investing + Income Strategy
stocks = client.screen_stocks(
    filters={
        'pe_ratio_max': 15,              # P/E rẻ
        'pb_ratio_max': 1.5,             # P/B hợp lý
        'roe_min': 15,                   # ROE cao
        'dividend_yield_min': 2,         # Chia cổ tức
        'debt_ratio_max': 40,            # Tài chính vững
        'price_min': 20,                 # Giá >= 20k
        'volume_min': 1000000            # Khối lượng tốt
    },
    sort_by='roe',
    order='descending'
)

print(stocks)
```

**Ví dụ: Tìm cổ phiếu tăng trưởng mạnh**

```python
# Growth Strategy
stocks = client.screen_stocks(
    filters={
        'revenue_growth_min': 15,        # Doanh thu tăng > 15%
        'profit_growth_min': 15,         # Lợi nhuận tăng > 15%
        'roe_min': 10,                   # ROE tối thiểu
        'debt_ratio_max': 50,            # Nợ không quá cao
        'current_ratio_min': 1.2         # Thanh khoản đủ
    },
    sort_by='profit_growth',
    order='descending'
)

print(stocks)
```

### Lưu kết quả Lọc

```python
import pandas as pd

stocks = client.screen_stocks(...)

# Lưu vào file CSV
stocks.to_csv('screened_stocks.csv', index=False)

# Lưu vào Excel
stocks.to_excel('screened_stocks.xlsx', index=False)

print(f"Tìm thấy {len(stocks)} cổ phiếu thỏa mãn tiêu chí")
```

### Cập nhật Lọc Định kỳ

```python
import schedule
import time

def daily_screening():
    stocks = client.screen_stocks(
        filters={
            'pe_ratio_max': 15,
            'roe_min': 15,
            'dividend_yield_min': 2
        }
    )
    
    # Lưu kết quả
    stocks.to_csv(f'screened_{pd.Timestamp.now().date()}.csv')
    print(f"Đã lưu {len(stocks)} cổ phiếu")

# Chạy mỗi ngày lúc 15:30
schedule.every().day.at("15:30").do(daily_screening)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Danh sách Tiêu chí Lọc Hỗ trợ

| Danh mục | Tiêu chí | Kiểu dữ liệu |
|----------|----------|-------------|
| **Giá** | price_min, price_max | float |
| **Khối lượng** | volume_min, volume_max | int |
| **Định giá** | pe_ratio_min, pe_ratio_max, pb_ratio_min, pb_ratio_max, ps_ratio_min, ps_ratio_max | float |
| **Cổ tức** | dividend_yield_min, dividend_yield_max, payout_ratio_min, payout_ratio_max | float |
| **Lợi suất** | roe_min, roe_max, roa_min, roa_max | float |
| **Margin** | net_margin_min, net_margin_max, gross_margin_min, gross_margin_max | float |
| **Thanh khoản** | current_ratio_min, current_ratio_max, quick_ratio_min, quick_ratio_max | float |
| **Nợ** | debt_ratio_min, debt_ratio_max, debt_to_equity_min, debt_to_equity_max | float |
| **Tăng trưởng** | revenue_growth_min, revenue_growth_max, profit_growth_min, profit_growth_max | float |
| **Kỹ thuật** | price_above_sma, price_above_ema, rsi_min, rsi_max | bool/float |
| **Phân loại** | sector, industry, index, exchange | string |

## Tài liệu liên quan

- [3. Phân tích cơ bản & Định giá](/ham-va-cong-thuc/3.-phan-tich-co-ban-and-dinh-gia.md)
- [8. Danh sách chỉ báo TA](/ham-va-cong-thuc/8.-danh-sach-chi-so-ta.md)
