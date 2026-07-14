# Python - Cấu trúc Dữ liệu & Thực hành Tốt nhất

## Phần 30: Python Data Structures & Best Practices

### 1. Cấu trúc Dữ liệu Chính

#### DataFrame (Khung dữ liệu)

```python
import pandas as pd
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lấy dữ liệu - kết quả trả về là DataFrame
df = client.get_historical_data(
    symbol='HPG',
    from_date='2024-01-01',
    to_date='2024-01-31',
    resolution='1D'
)

# DataFrame có cấu trúc:
# - Index: Ngày (datetime)
# - Columns: open, high, low, close, volume

print(type(df))  # <class 'pandas.core.frame.DataFrame'>
print(df.shape)  # (20, 5) - 20 hàng, 5 cột
print(df.dtypes)

# Inspect DataFrame
print(df.head())      # 5 hàng đầu
print(df.tail())      # 5 hàng cuối
print(df.info())      # Thông tin chi tiết
print(df.describe())  # Thống kê

# Truy cập dữ liệu
print(df['close'])                    # Column 'close'
print(df.loc['2024-01-15'])           # Row ngày 2024-01-15
print(df.loc['2024-01-15', 'close'])  # Một ô cụ thể
```

#### Series (Chuỗi dữ liệu)

```python
# Series là một cột dữ liệu
close_prices = df['close']
print(type(close_prices))  # <class 'pandas.core.series.Series'>

# Toán học với Series
returns = close_prices.pct_change()  # Thay đổi %
sma_20 = close_prices.rolling(20).mean()  # Trung bình động

# Statistics
print(close_prices.mean())     # Trung bình
print(close_prices.std())      # Độ lệch chuẩn
print(close_prices.min())      # Tối thiểu
print(close_prices.max())      # Tối đa
print(close_prices.median())   # Trung vị
```

#### Dictionary (Từ điển)

```python
# Dữ liệu realtime thường trả về dạng Dictionary
realtime_quote = client.get_realtime_quote('HPG')

print(type(realtime_quote))  # <class 'dict'>
print(realtime_quote)
# Output:
# {
#     'symbol': 'HPG',
#     'close': 45.5,
#     'volume': 2500000,
#     'time': '15:00:00'
# }

# Truy cập Dictionary
price = realtime_quote['close']
symbol = realtime_quote['symbol']

# Thêm/sửa giá trị
realtime_quote['status'] = 'active'

# Kiểm tra key tồn tại
if 'dividend' in realtime_quote:
    dividend = realtime_quote['dividend']
```

#### List (Danh sách)

```python
# Danh sách các mã
symbols = client.get_symbols_by_index('VN30')
print(type(symbols))  # <class 'list'>

# Duyệt danh sách
for symbol in symbols:
    print(symbol)

# List comprehension
vn30_codes = [s for s in symbols]

# Thêm/xóa
symbols.append('NEW')
symbols.remove('HPG')

# Lấy độ dài
num_symbols = len(symbols)
```

### 2. Xử lý Dữ liệu với Pandas

#### Lọc Dữ liệu

```python
# Lọc hàng (rows)
df_high_volume = df[df['volume'] > 2000000]
df_high_price = df[df['close'] > 45]

# Lọc nhiều điều kiện
df_filtered = df[
    (df['close'] > 44) & 
    (df['volume'] > 1500000) &
    (df['high'] > 46)
]

# Lọc cột (columns)
df_subset = df[['close', 'volume']]

# Lọc theo index (ngày)
df_after = df['2024-01-15':]  # Từ 15/1 trở đi
df_period = df['2024-01-10':'2024-01-20']  # Khoảng 10-20/1
```

#### Thêm Cột Mới

```python
# Tính lợi nhuận hàng ngày
df['returns'] = df['close'].pct_change()

# Tính trung bình động
df['sma_20'] = df['close'].rolling(window=20).mean()
df['sma_50'] = df['close'].rolling(window=50).mean()

# Tính độ dao động
df['volatility'] = df['returns'].rolling(window=20).std()

# Tính highest/lowest
df['highest_20'] = df['high'].rolling(window=20).max()
df['lowest_20'] = df['low'].rolling(window=20).min()

# Điều kiện
df['uptrend'] = df['close'] > df['sma_20']  # True/False
```

#### Tính Toán Tổng Hợp

```python
# Tổng
total_volume = df['volume'].sum()

# Trung bình
avg_price = df['close'].mean()

# Cao/Thấp
highest_price = df['high'].max()
lowest_price = df['low'].min()

# Nhóm & Tính toán
df['month'] = df.index.month
monthly_return = df.groupby('month')['returns'].sum()
```

#### Kết Hợp Dữ liệu

```python
# Lấy dữ liệu 2 mã khác nhau
df_hpg = client.get_historical_data('HPG', '2024-01-01', '2024-01-31', '1D')
df_vnm = client.get_historical_data('VNM', '2024-01-01', '2024-01-31', '1D')

# Kết hợp (inner join - chỉ ngày trùng)
df_merged = pd.merge(
    df_hpg[['close']].rename(columns={'close': 'HPG'}),
    df_vnm[['close']].rename(columns={'close': 'VNM'}),
    left_index=True,
    right_index=True,
    how='inner'
)

# Hoặc dùng concat
df_combined = pd.concat([
    df_hpg[['close']].rename(columns={'close': 'HPG'}),
    df_vnm[['close']].rename(columns={'close': 'VNM'})
], axis=1)
```

### 3. Lưu & Đọc Dữ liệu

#### Lưu vào File

```python
# Lưu CSV
df.to_csv('data.csv', index=True)

# Lưu Excel
df.to_excel('data.xlsx', sheet_name='Historical Data')

# Lưu JSON
df.to_json('data.json')

# Lưu Pickle (fast, binary)
df.to_pickle('data.pkl')
```

#### Đọc từ File

```python
# Đọc CSV
df_csv = pd.read_csv('data.csv', index_col=0, parse_dates=True)

# Đọc Excel
df_excel = pd.read_excel('data.xlsx', sheet_name='Historical Data')

# Đọc JSON
df_json = pd.read_json('data.json')

# Đọc Pickle
df_pickle = pd.read_pickle('data.pkl')
```

### 4. Xử lý Lỗi (Error Handling)

#### Try-Except

```python
# Xử lý lỗi kết nối
try:
    df = client.get_historical_data(
        symbol='HPG',
        from_date='2024-01-01',
        to_date='2024-01-31',
        resolution='1D'
    )
except Exception as e:
    print(f"Lỗi: {e}")
    df = None

# Xử lý lỗi xác thực
from FiinQuantX.errors import AuthenticationError

try:
    client = FiinSession(username='user', password='pass').login()
except AuthenticationError:
    print("Username hoặc password không đúng")
```

#### Kiểm Tra Dữ liệu

```python
# Kiểm tra NaN (dữ liệu thiếu)
print(df.isnull().sum())  # Số lượng NaN trong mỗi cột

# Loại bỏ NaN
df_clean = df.dropna()

# Điền NaN với giá trị
df['returns'].fillna(0)

# Kiểm tra duplicates
print(df.duplicated().sum())
df_unique = df.drop_duplicates()
```

### 5. Vòng Lặp Hiệu quả

#### Loop qua Symbols

```python
import time

symbols = ['HPG', 'VNM', 'ACB', 'VCB', 'TCB']
all_data = {}

for i, symbol in enumerate(symbols):
    try:
        df = client.get_historical_data(
            symbol=symbol,
            from_date='2024-01-01',
            to_date='2024-01-31',
            resolution='1D'
        )
        all_data[symbol] = df
        
        print(f"({i+1}/{len(symbols)}) Lấy {symbol}: OK")
        time.sleep(1)  # Rate limit
        
    except Exception as e:
        print(f"({i+1}/{len(symbols)}) Lấy {symbol}: FAILED - {e}")

print(f"Tổng lấy được: {len(all_data)} mã")
```

#### Vectorization (Thay vì loop)

```python
# Tệ: Loop dòng dòng
result = []
for idx, row in df.iterrows():
    result.append(row['close'] * row['volume'])

# Tốt: Vectorization
df['value'] = df['close'] * df['volume']
```

### 6. Hàm Tái sử dụng

#### Hàm Lấy Dữ liệu

```python
def get_stock_data(symbol, from_date, to_date, resolution='1D'):
    """
    Lấy dữ liệu lịch sử của cổ phiếu
    
    Parameters:
    -----------
    symbol : str
        Mã cổ phiếu (e.g., 'HPG')
    from_date : str
        Ngày bắt đầu (YYYY-MM-DD)
    to_date : str
        Ngày kết thúc (YYYY-MM-DD)
    resolution : str
        Khung thời gian ('1D', '1W', '1M')
    
    Returns:
    --------
    DataFrame
        Dữ liệu OHLCV
    """
    try:
        df = client.get_historical_data(
            symbol=symbol,
            from_date=from_date,
            to_date=to_date,
            resolution=resolution
        )
        return df
    except Exception as e:
        print(f"Lỗi lấy dữ liệu {symbol}: {e}")
        return None

# Sử dụng
df = get_stock_data('HPG', '2024-01-01', '2024-01-31')
```

#### Hàm Phân tích

```python
def analyze_stock(symbol, from_date, to_date):
    """
    Phân tích toàn bộ một cổ phiếu
    """
    
    df = get_stock_data(symbol, from_date, to_date)
    if df is None:
        return None
    
    # Tính chỉ báo
    df['returns'] = df['close'].pct_change()
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    
    # Thống kê
    stats = {
        'symbol': symbol,
        'avg_price': df['close'].mean(),
        'highest_price': df['close'].max(),
        'lowest_price': df['close'].min(),
        'avg_volume': df['volume'].mean(),
        'annual_return': df['returns'].mean() * 252,
        'annual_volatility': df['returns'].std() * np.sqrt(252),
        'trend': 'UP' if df['close'].iloc[-1] > df['sma_50'].iloc[-1] else 'DOWN'
    }
    
    return stats

# Sử dụng
stats = analyze_stock('HPG', '2024-01-01', '2024-01-31')
print(stats)
```

### 7. Thực hành Tốt nhất

#### 1. **Quản lý Phiên làm việc**

```python
# Luôn đăng nhập khi bắt đầu
from FiinQuantX import FiinSession

client = FiinSession(
    username='your_username',
    password='your_password'
).login()

# Kiểm tra đăng nhập thành công
print(client.is_authenticated)  # True

# Logout khi kết thúc
client.logout()
```

#### 2. **Lưu Log**

```python
import logging

logging.basicConfig(
    filename='fiinquant.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

try:
    df = client.get_historical_data('HPG', '2024-01-01', '2024-01-31', '1D')
    logger.info("Successfully fetched HPG data")
except Exception as e:
    logger.error(f"Failed to fetch HPG data: {e}")
```

#### 3. **Cache Dữ liệu**

```python
import pickle
import os
from datetime import datetime

def get_cached_data(symbol, from_date, to_date, cache_dir='cache'):
    """
    Lấy dữ liệu từ cache nếu tồn tại, ngược lại lấy từ API
    """
    
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = f"{cache_dir}/{symbol}_{from_date}_{to_date}.pkl"
    
    # Nếu file cache tồn tại và không quá 1 ngày cũ
    if os.path.exists(cache_file):
        file_age = datetime.now().timestamp() - os.path.getmtime(cache_file)
        if file_age < 86400:  # 1 ngày
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
    
    # Lấy từ API
    df = client.get_historical_data(symbol, from_date, to_date, '1D')
    
    # Lưu cache
    with open(cache_file, 'wb') as f:
        pickle.dump(df, f)
    
    return df
```

#### 4. **Validation Dữ liệu**

```python
def validate_dataframe(df, required_columns=['open', 'high', 'low', 'close', 'volume']):
    """
    Kiểm tra DataFrame có đầy đủ cột và không có NaN
    """
    
    # Kiểm tra cột
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing columns: {missing_columns}")
    
    # Kiểm tra NaN
    if df.isnull().any().any():
        raise ValueError("DataFrame contains NaN values")
    
    # Kiểm tra dữ liệu
    if (df['high'] < df['low']).any():
        raise ValueError("High price less than low price")
    
    if (df['volume'] < 0).any():
        raise ValueError("Negative volume")
    
    return True

# Sử dụng
df = client.get_historical_data('HPG', '2024-01-01', '2024-01-31', '1D')
validate_dataframe(df)
```

## Tài liệu liên quan

- [Đăng nhập tài khoản](/tai-lieu-ki-thuat/dang-nhap-tai-khoan.md)
- [Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
- [Ứng dụng thực tế](/thuc-tien-ap-dung/21.-lay-du-lieu-phan-tich-chien-luoc-giao-dich.md)
