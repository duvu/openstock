# Hàm và Công thức - Hướng dẫn sử dụng

## Phần 1: Danh mục & Thông tin cơ bản

FiinQuant cung cấp các hàm để lấy danh mục cổ phiếu và thông tin cơ bản về các mã.

### 1.1. Danh sách mã theo index

**Mô tả:**
Lấy danh sách các mã cổ phiếu theo chỉ số (VN100, VN30, HNXIndex, UpcomIndex, v.v.)

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession

client = FiinSession(username='your_username', password='your_password').login()

# Lấy danh sách mã VN30
vn30_list = client.get_symbols_by_index('VN30')

# Lấy danh sách mã VN100
vn100_list = client.get_symbols_by_index('VN100')

# Lấy danh sách mã HNX
hnx_list = client.get_symbols_by_index('HNX')

print(vn30_list)
```

**Tham số:**
- `index` (string): Tên chỉ số (VN30, VN100, HNXIndex, UpcomIndex)

**Kết quả trả về:**
- Danh sách các mã cổ phiếu trong chỉ số
- Trọng số của từng mã (nếu có)

### 1.2. Danh sách mã theo ngành

**Mô tả:**
Lấy danh sách các mã cổ phiếu theo ngành công nghiệp (ICB Classification)

**Hàm sử dụng:**
```python
# Lấy danh sách mã theo ngành
sector = 'Financials'  # Ngành Tài chính
stocks = client.get_symbols_by_sector(sector)

# Hoặc lấy tất cả ngành
all_sectors = client.get_all_sectors()
for sector in all_sectors:
    stocks = client.get_symbols_by_sector(sector)
    print(f"{sector}: {len(stocks)} mã")
```

**Tham số:**
- `sector` (string): Tên ngành công nghiệp

**Danh sách các ngành chính:**
- Technology (Công nghệ)
- Financials (Tài chính)
- Healthcare (Y tế)
- Consumer Discretionary (Hàng tiêu dùng tùy ý)
- Industrials (Công nghiệp)
- Materials (Nguyên liệu)
- Energy (Năng lượng)
- Utilities (Dịch vụ tiện ích)
- Real Estate (Bất động sản)
- Consumer Staples (Hàng tiêu dùng thiết yếu)

### 1.3. Danh sách mã theo tỷ trọng

**Mô tả:**
Lấy danh sách các mã cổ phiếu theo tỷ trọng hoặc quy mô thị trường (Market Cap)

**Hàm sử dụng:**
```python
# Lấy danh sách mã theo quy mô (Market Cap)
large_cap = client.get_symbols_by_marketcap('large')   # Vốn hóa lớn
mid_cap = client.get_symbols_by_marketcap('mid')       # Vốn hóa vừa
small_cap = client.get_symbols_by_marketcap('small')   # Vốn hóa nhỏ

print(f"Large Cap: {len(large_cap)} mã")
print(f"Mid Cap: {len(mid_cap)} mã")
print(f"Small Cap: {len(small_cap)} mã")
```

### 1.4. Lấy dữ liệu vốn hóa

**Mô tả:**
Lấy dữ liệu vốn hóa thị trường (Market Capitalization) của từng mã cổ phiếu

**Hàm sử dụng:**
```python
# Lấy vốn hóa của một mã
marketcap = client.get_market_cap('HPG')
print(f"Market Cap of HPG: {marketcap}")

# Lấy vốn hóa realtime (trong phiên giao dịch)
realtime_marketcap = client.get_market_cap_realtime('HPG')
print(f"Realtime Market Cap: {realtime_marketcap}")

# Lấy vốn hóa của nhiều mã
symbols = ['HPG', 'VNM', 'ACB']
marketcaps = client.get_market_caps(symbols)
print(marketcaps)
```

**Công thức tính:**
```
Market Cap = Giá đóng cửa × Số lượng cổ phiếu phát hành
```

### 1.5. Lấy dữ liệu room NĐTNN

**Mô tả:**
Lấy dữ liệu phòng (room) của nhà đầu tư nước ngoài - thông tin về lượng ngoại tệ còn lại có thể mua

**Hàm sử dụng:**
```python
# Lấy dữ liệu room NĐTNN
room = client.get_foreign_room('HPG')

# Lấy realtime room (trong phiên giao dịch)
realtime_room = client.get_foreign_room_realtime('HPG')

# Lấy room của nhiều mã
symbols = ['HPG', 'VNM', 'ACB']
rooms = client.get_foreign_rooms(symbols)
print(rooms)
```

**Thông tin trả về:**
- Room còn lại (VND)
- Room đã sử dụng (VND)
- Tỷ lệ room đã sử dụng (%)

### 1.6. Lấy dữ liệu Freefloat

**Mô tả:**
Lấy dữ liệu cổ phiếu tự do (Free Float) - cổ phiếu có thể giao dịch trên thị trường

**Hàm sử dụng:**
```python
# Lấy dữ liệu freefloat
freefloat = client.get_freefloat('HPG')

# Lấy freefloat của nhiều mã
symbols = ['HPG', 'VNM', 'ACB']
freefloats = client.get_freefloats(symbols)
print(freefloats)
```

**Công thức tính:**
```
Free Float = Số cổ phiếu tự do / Tổng cổ phiếu phát hành × 100%
```

### 1.7. Lấy dữ liệu giá trần, giá sàn

**Mô tả:**
Lấy dữ liệu giá trần và giá sàn của từng mã cổ phiếu (được xác định bởi các sở giao dịch)

**Hàm sử dụng:**
```python
# Lấy giá trần và giá sàn
ceiling = client.get_price_ceiling('HPG')
floor = client.get_price_floor('HPG')

# Lấy cả hai
price_limits = client.get_price_limits('HPG')
print(f"Ceiling: {price_limits['ceiling']}")
print(f"Floor: {price_limits['floor']}")

# Lấy cho nhiều mã
symbols = ['HPG', 'VNM', 'ACB']
limits = client.get_price_limits_batch(symbols)
```

### 1.8. Lấy dữ liệu giao dịch theo nhà đầu tư

**Mô tả:**
Lấy dữ liệu phân loại giao dịch theo các loại nhà đầu tư (Nhà đầu tư tổ chức, cá nhân, nước ngoài, v.v.)

**Hàm sử dụng:**
```python
# Lấy dữ liệu giao dịch theo nhà đầu tư
investor_data = client.get_transaction_by_investor('HPG', '2024-01-01')

# Các loại nhà đầu tư
# - Institutional Investors (Tổ chức)
# - Individual Investors (Cá nhân)
# - Foreign Investors (Nước ngoài)
# - Other (Khác)

print(investor_data)
```

**Dữ liệu trả về:**
- Khối lượng mua/bán
- Giá trung bình
- Giá trị giao dịch

### 1.9. Lấy dữ liệu thông tin cơ bản của cổ phiếu

**Mô tả:**
Lấy thông tin cơ bản: Tên doanh nghiệp, sàn giao dịch, ngành công nghiệp

**Hàm sử dụng:**
```python
# Lấy thông tin cơ bản
info = client.get_stock_info('HPG')

print(f"Tên: {info['company_name']}")
print(f"Sàn: {info['exchange']}")  # HOSE, HNX, UPCOM
print(f"Ngành: {info['sector']}")
print(f"Cấp 2: {info['industry']}")
print(f"Cấp 3: {info['sub_industry']}")

# Lấy thông tin của nhiều mã
symbols = ['HPG', 'VNM', 'ACB']
infos = client.get_stocks_info(symbols)
```

**Thông tin trả về:**
- Tên công ty
- Mã sàn
- Mã ngành
- Mã ngành cấp 2
- Tính chất hoạt động (phức hợp, phát triển...)

## Kết nối

Để sử dụng các hàm này, bạn cần:

1. ✅ Cài đặt FiinQuant: `pip install fiinquantx`
2. ✅ Đăng nhập với tài khoản của bạn
3. ✅ Gọi các hàm phù hợp

## Tài liệu liên quan

- [Đăng nhập tài khoản](/tai-lieu-ki-thuat/dang-nhap-tai-khoan.md)
- [Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
