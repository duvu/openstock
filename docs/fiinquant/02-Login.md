# Đăng nhập tài khoản

## Quản lý phiên đăng nhập

### Tham số yêu cầu

| Tham số  | Mô tả                        | Loại dữ liệu |
| -------- | ---------------------------- | ------------ |
| username | Tên đăng nhập của người dùng | String       |
| password | Mật khẩu của người dùng      | String       |

### Mã lỗi

| Lỗi                                     | Mã   | Mô tả                        |
| --------------------------------------- | ---- | ---------------------------- |
| User does not exist (Tài khoản không tồn tại) | 400  | Người dùng nhập sai username |
| Incorrect password (Mật khẩu không đúng) | 400  | Người dùng nhập sai password |

## Hướng dẫn đăng nhập

### Cách 1: Sử dụng FiinSession

```python
from FiinQuantX import FiinSession

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(
    username=username,
    password=password,
).login()
```

### Cách 2: Lưu credentials trong biến môi trường

```python
import os
from FiinQuantX import FiinSession

username = os.getenv('FIINQUANT_USERNAME')
password = os.getenv('FIINQUANT_PASSWORD')

client = FiinSession(
    username=username,
    password=password,
).login()
```

## Xử lý lỗi đăng nhập

```python
from FiinQuantX import FiinSession
from FiinQuantX.errors import AuthenticationError

username = 'your_username'
password = 'your_password'

try:
    client = FiinSession(
        username=username,
        password=password,
    ).login()
    print("Đăng nhập thành công!")
except AuthenticationError as e:
    print(f"Lỗi đăng nhập: {e}")
```

## Kiểm tra trạng thái đăng nhập

Sau khi đăng nhập thành công, bạn có thể sử dụng `client` để gọi các hàm khác của FiinQuant.
