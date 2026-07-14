# Truy xuất dữ liệu

## Truy xuất dữ liệu lịch sử

```python
from FiinQuantX import FiinSession
# Đăng nhập
username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(username=username, password=password).login()
fi = client.FiinIndicator()
# Lấy dữ liệu có sẵn
tickers = ['HPG','SSI','VN30'] 
df = client.Fetch_Trading_Data(
    realtime = False,
    tickers = tickers,    
    fields = ['open','high','low','close','volume','bu','sd','fn','fs','fb'],
    adjusted=True,
    from_date='2024-12-04',
    by = '1m'
    ).get_data()

print(df)
```

```
 fields = ['open','high','low','close','volume','bu','sd','fn','fs','fb']
```

Giải thích các trường dữ liệu:

* open,high,low,close: Đại diện cho giá Open, High, Low, Close
* volume: Đại diện cho khối lượng khớp lệnh (Volume)
* bu,sd: Chỉ số mua bán chủ động
* fn,fs,fb: là Foreign Net, Foreign Sell, Foreign Buy, giá trị nhà đầu tư nước ngoài mua bán ròng, mua hoặc bán.

## Truy xuất dữ liệu Realtime

```python
import time
import pandas as pd

from FiinQuantX import FiinSession, RealTimeData

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(username=username, password=password).login()

fi = client.FiinIndicator()
df = []
tickers = ['SSI','ITC','HPG','VHM']
for i in range(len(tickers)):
    df.append(pd.DataFrame())
df_total = pd.DataFrame()
def onEvent(data: RealTimeData):
    global df_total
    df_total = pd.concat([df_total, data.to_dataFrame()],ignore_index=True)
    df_total.to_csv('data.csv', index = False)
    for i in range(len(tickers)):
        if data.Ticker == tickers[i]:
            print(data.Ticker, data.Close)
            df[i] = pd.concat([df[i], data.to_dataFrame()],ignore_index=True)
            print(df[i])

TickerEvents = client.Trading_Data_Stream(tickers=tickers, callback = onEvent)
TickerEvents.start()
try:
    while not TickerEvents._stop:
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt received, stopping...")
    TickerEvents.stop()

```

## 3. Tìm khối lượng mua bán ATC của VN30

<figure><img src="/files/6Z7jJKbMtt4IVLJNWwHj" alt=""><figcaption><p>VN30 khối lượng ATC</p></figcaption></figure>

```python

import pandas as pd
from FiinQuantX import FiinSession

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(
    username=username,
    password=password
).login()

VN30 = [
    'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
    'LPB', 'MBB', 'MSN', 'MWG', 'PLX', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE']
 

data = client.Fetch_Trading_Data(
    tickers=VN30,
    fields=['fn', 'fs', 'fb'],
    adjusted=True,
    period=10,
    realtime=False,
    by='1m',
).get_data()

filtered_data = data[data['timestamp'].str.endswith('14:45')]
filtered_data.to_excel('filtered_data.xlsx', index=False)
print("Data stored in filtered_data.xlsx")
```
