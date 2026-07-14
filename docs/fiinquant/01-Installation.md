# Cài đặt và chuẩn bị

## 1. Cài đặt Python trên Windows

### Cài đặt từ Python.org (Khuyến nghị)

#### Bước 1: Tải Python
1. Truy cập [Trang chủ Python](https://www.python.org/downloads/windows/)
2. Nhấn Download Python (Phiên bản mới nhất)

#### Bước 2: Cài đặt Python
1. Mở file .exe vừa tải về.
2. **Chọn "Add Python to PATH"** - Đây là bước quan trọng
3. Nhấn Install Now và đợi quá trình cài đặt hoàn tất.

#### Bước 3: Kiểm tra cài đặt
Mở Command Prompt (CMD) và nhập:
```bash
python --version
```

## 2. Cài đặt thư viện FiinQuant

### Cài đặt FiinQuantX
```bash
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

### Cập nhật thư viện khi có phiên bản mới
```bash
pip install --upgrade --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

### Lưu ý quan trọng
⚠️ **KHÔNG ĐẶT TÊN CÁC FILE SCRIPT PYTHON TRÙNG VỚI TÊN THƯ VIỆN (FiinQuant)**

Ví dụ: Không tạo file tên `FiinQuant.py` hoặc `fiinquantx.py`

## 3. Xác minh cài đặt

Tạo file `test_install.py` với nội dung:
```python
from FiinQuantX import FiinSession

print("FiinQuantX installed successfully!")
```

Chạy file:
```bash
python test_install.py
```

Nếu không có lỗi, cài đặt thành công ✅
