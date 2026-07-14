# Truy xuất và lưu dữ liệu realtime lên Google Sheet

## Tạo và tải khóa tài khoản dịch vụ Google JSON

Đi đến Google Cloud Console: <https://console.cloud.google.com/>

Chọn hoặc tạo một project mới, nếu không có project nào click "New Project".

<figure><img src="/files/Z49VincTfBth7zggDULW" alt=""><figcaption></figcaption></figure>

Đi đến mục **APIs & Services > Library**

<figure><img src="/files/gf3V0bRZuh6tXXmTULM3" alt=""><figcaption></figcaption></figure>

<figure><img src="/files/GLozvc66M7s9OVOSSG6y" alt=""><figcaption></figcaption></figure>

Chọn mục **Google Sheets API**

<figure><img src="/files/w8H5dfVhaONPSb1a2AWx" alt=""><figcaption></figcaption></figure>

Enable API

<figure><img src="/files/sDzeKFH6s0aQ9rStCBfM" alt=""><figcaption></figcaption></figure>

Truy cập vào mục **IAM & Admin > Service Accounts**, click **"Create Service Account"**, thực hiện đặt tên chp Service Account rồi click "Create and Continue"

<figure><img src="/files/UF1NI0MVcI8UgCd59Zbh" alt=""><figcaption></figcaption></figure>

Chọn role cho Service Account (Editor) và click Continue

<figure><img src="/files/4eOilJoWXGvKbNBVLQYR" alt=""><figcaption></figcaption></figure>

Sau khi tạo Service Account, click vào tên Service Account mới tạo, đi đến tab **"Keys"**, click **"Add Key" > "Create new key"**, chọn **JSON** và click **"Create"**. Sau đó trình duyệt sẽ tải file JSON cấu hình để truy cập vào Google Sheet tự động. Sau đó hãy di chuyển file JSON vừa tải về đến cùng folder với file Python viết code Truy xuất data từ FiinQuant và lưu lên Google Sheets.

Sau đó thực hiện truy cập vào file Google Sheets cần load data lên, thực hiện add quyền edit cho email ở mục **client\_email** của file JSON vừa tải về. Sau đó thực hiện đoạn code sau

<pre class="language-python"><code class="lang-python">import os
import gspread
import time
import pandas as pd

from FiinQuantX import FiinSession, RealTimeData
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials

username = "REPLACE_WITH_YOUR_USERNAME"
password = "REPLACE_WITH_YOUR_PASSWORD"

client_fq = FiinSession(
    username = username,
    password = password
).login()

def OnTickerEvent(data: RealTimeData):
    global full_df
    df = data.to_dataFrame()
    
    # Xác thực và kết nối đến Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("REPLACE_WITH_JSON_FILE_NAME")
    client = gspread.authorize(creds)

    # Mở Google Sheet và chọn worksheet
    sheet = client.open("REPLACE_WITH_YOUR_GOOGLE_SHEET_FILE_NAME").worksheet("REPLACE_WITH_SHEET_NAME")

    # Thêm data vào Google Sheet ---
    existing_rows = len(sheet.get_all_values())  # Đếm số cột hiện có
    
    # Nếu chưa có cột nào thêm data mới bao gồm cả tiêu đề cột, nếu không chỉ thêm data, không thêm tiêu đề cột
    if existing_rows &#x3C;= 1:
        set_with_dataframe(sheet, df, row=existing_rows, include_column_header=True)
    else:
        set_with_dataframe(sheet, df, row=existing_rows + 1, include_column_header=False)

<strong>tickers = ['STB', 'FPT', 'MSN', 'HPG']
</strong>
event = client_fq.Trading_Data_Stream(tickers=tickers, callback=OnTickerEvent)
event.start()

try:
    while not event._stop: 
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt received, stopping...")
    event.stop()


</code></pre>
