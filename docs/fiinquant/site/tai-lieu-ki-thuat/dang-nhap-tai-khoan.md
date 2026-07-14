# Đăng nhập tài khoản

**Quản lý phiên đăng nhập**

<br>

| Tham số  | Mô tả                        |
| -------- | ---------------------------- |
| username | Tên đăng nhập của người dùng |
| password | Mật khẩu của người dùng      |

**Phương thức**

| Tên phương thức                               | Mã lỗi | Mô tả                                    |
| --------------------------------------------- | ------ | ---------------------------------------- |
| User does not exist (Tài khoản không tồn tại) | 400    | <p>Người dùng nhập sai username.<br></p> |
| Incorrect password (Mật khẩu không đúng)      | 400    | Người dùng nhập sai password.            |

Truy cập phiên đăng nhập

<pre class="language-python"><code class="lang-python"><strong>from FiinQuantX import FiinSession
</strong>

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(
    username=username,
    password=password,
).login()
</code></pre>
