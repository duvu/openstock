# Data retrieval

## Historical data retrieval

```python
import FiinQuantX as fq
# Đăng nhập
username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(username=username, password=password).login()
fi = client.FiinIndicator()
# Lấy dữ liệu có sẵn
tickers = ['HPG','SSI','VN30'] 
event = client.Fetch_Trading_Data(
    realtime = False,
    tickers = tickers,    
    fields = ['open','high','low','close','volume','bu','sd','fn','fs','fb'],
    adjusted=True,  
    # period=10,
    from_date='2024-12-04',
    by = '1m'
    )
df = event.get_data()
print(df)
```

```
 fields = ['open','high','low','close','volume','bu','sd','fn','fs','fb']
```

Explanation of data fields:

* **open**, **high**, **low**, **close**: Represent open, high, low, close prices.
* **volume**: Represents matching order volume.
* **bu**, **sd**: Active buy/sell indicators.
* **fn**, **fs**, **fb**: Foreign net, foreign sell, foreign buy, representing foreign investor net buy/sell, buy, or sell values.

## Real-time data retrieval

```python
import time
import pandas as pd
import FiinQuantX as fq

from FiinQuantX import RealTimeData

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(username=username, password=password).login()

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

## Find the ATC buy/sell volume of VN30

<figure><img src="/files/6Z7jJKbMtt4IVLJNWwHj" alt=""><figcaption><p>VN30 ATC volume</p></figcaption></figure>

```python

import pandas as pd
from FiinQuantX import FiinSession

username = 'YOUR USERNAME HERE'
password = 'YOUR PASSWORD HERE'
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
