# Cài đặt và chuẩn bị

<figure><img src="/files/ll4cukib6lzGJ5g1BRfH" alt=""><figcaption></figcaption></figure>

### 1. Cài đặt Python trên Windows 🖥️

Cài đặt từ Python.org (Khuyến nghị)

{% stepper %}
{% step %}
**📌  Tải Python**

&#x20;Truy cập [Trang chủ Python](https://www.python.org/downloads/windows/)

Nhấn Download Python (Phiên bản mới nhất)
{% endstep %}

{% step %}
**📌 Cài đặt Python**

Mở file .exe vừa tải về.

Chọn “Add Python to PATH”

Nhấn Install Now và đợi quá trình cài đặt hoàn tất.
{% endstep %}

{% step %}
**📌 Kiểm tra cài đặt**

Mở Command Prompt (CMD) và nhập:

```
python --version
```

{% endstep %}
{% endstepper %}

### 2. Cài đặt thư viện FiinQuant. <a href="#cai-dat-thu-vien-fiinquant" id="cai-dat-thu-vien-fiinquant"></a>

```
pip install --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

Cập nhật thư viện khi có phiên bản mới.

```
pip install --upgrade --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

**Lưu ý:** KHÔNG ĐẶT TÊN CÁC FILE SCRIPT PYTHON TRÙNG VỚI TÊN THƯ VIỆN (FiinQuant).\ <br>
