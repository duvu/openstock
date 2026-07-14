# Các lỗi thường gặp

1. ### Lỗi ImportError

<figure><img src="/files/fwg9VDRc8gJhMXdL0NX7" alt=""><figcaption><p>Import Error</p></figcaption></figure>

**Nguyên nhân 11:**

Windows Defender có thể xóa hoặc cách ly file, vì vậy người dùng cần khôi phục nó trước khi chạy lại code.

Cách khôi phục file từ Quarantine:

1\. Mở Windows Security bằng cách nhấn Win + S, gõ “Windows Security”, rồi mở ứng dụng.

2\. Vào “Virus & threat protection”.

3\. Nhấp vào “Protection history”.

4\. Tìm mục “Threat quarantined” liên quan đến FiinQuant\\\_\_init\_\_.py.

5\. Nhấp vào “Actions” → Chọn “Restore”.

🔹 Lưu ý: Nếu Windows Defender tự động xóa file, bạn cần cài lại thư viện FiinQuant sau khi khôi phục.
