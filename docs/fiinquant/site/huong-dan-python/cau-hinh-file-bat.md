# Cấu hình file bat

**I.   Tạo file Batch**&#x20;

1. Mở Notepad.&#x20;

<figure><img src="/files/5YH1MXF8OsMkHyFJIbtU" alt="" width="329"><figcaption></figcaption></figure>

2. Đánh đoạn code sau vào notepad:&#x20;

@echo off &#x20;

cd /d "C:\Path\To\Your\Python\Script" &#x20;

"C:\Path\To\Python\python.exe" script.py &#x20;

Exit&#x20;

<figure><img src="/files/aJVa95FtPDNe8EDepY1m" alt="" width="563"><figcaption></figcaption></figure>

* Thay "C:\Path\To\Your\Python\Script" bằng đường dẫn folder chứa file Python muốn chạy.&#x20;
* Thay "C:\Path\To\Python\python.exe" bằng đường dẫn đến file python.exe. Để tìm đường dẫn của file python.exe thực hiện nhấn Windows, tìm file gõ python.exe, nhấn chuột phải và chọn open file location.&#x20;

<figure><img src="/files/PXZ5UlArseN6K2wytjRN" alt="" width="563"><figcaption></figcaption></figure>

3. Lưu file theo cú pháp run\_script.bat (Đảm bảo là lựa chọn “All Files”)

<figure><img src="/files/CKT5f3PWOD4NQbB26hNI" alt=""><figcaption></figcaption></figure>

**II.   Đặt lịch bằng cách dùng Task Scheduler**&#x20;

1. Nhấn Win + R, đánh taskschd.msc và nhấn Enter.&#x20;

<figure><img src="/files/j3YDx1JagMhwCLX2jRsm" alt="" width="563"><figcaption></figcaption></figure>

2. Chọn Create Basis Task ở panel bên phải

<figure><img src="/files/Zx7w8Znv2f78WrCJKcw0" alt="" width="563"><figcaption></figcaption></figure>

3. Đặt tên cho task (VD: “Run Python Script”) và ấn Next (Có thể thêm mô tả nếu muốn).

<figure><img src="/files/XoNMPji7oOQ3Fxam54HH" alt="" width="563"><figcaption></figcaption></figure>

4. Chọn tần suất Trigger (VD: Hằng ngày, hang tuần, hàng tháng, v.v.) và ấn Next

<figure><img src="/files/jEmZdIClaDZPsazKX9WZ" alt="" width="563"><figcaption></figcaption></figure>

5. Đặt thời gian bắt đầu chạy vần ấn Next

<figure><img src="/files/jtyTYhHzvCoN3rDAL7Oi" alt="" width="563"><figcaption></figcaption></figure>

6. Chọn Start a Program và ấn Next

<figure><img src="/files/uTubcN4pNSsY6illw5rg" alt="" width="563"><figcaption></figcaption></figure>

7. Chọn Browse và tìm file mà bạn muốn đặt lịch chạy (VD: run\_script.bat)

<figure><img src="/files/vY9uAFcAgv3MdFQiq520" alt="" width="563"><figcaption></figcaption></figure>

8. Chọn Finish và lưu tác vụ
