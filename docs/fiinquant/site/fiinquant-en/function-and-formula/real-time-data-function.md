# Real-time data function

Describe how to use the library after logging in. Detailed examples are provided at the end of this chapter.

```python
Events = client.Trading_Data_Stream(tickers = tickers, callback = callback)
```

**Parameter**

<table><thead><tr><th>Name</th><th width="187">Description</th><th>Data type</th><th>Required</th></tr></thead><tbody><tr><td>tickers</td><td>Code name, including stock codes, index codes, derivative codes, and covered warrant codes. These codes are written in uppercase.</td><td><p>list [str]</p><p><br></p></td><td>Yes</td></tr><tr><td>callback</td><td>A user-defined function for data manipulation</td><td>function</td><td>Yes</td></tr></tbody></table>

The data receiving class is **Trading\_Data\_Stream**, with the following two methods:

<figure><img src="/files/YAC6Nv3mqcMFLlwm4Sma" alt=""><figcaption></figcaption></figure>

**callback function**

It's a user-defined method for data manipulation, which will be passed as an argument when initializing the data receiving object. This method will have the following format:

```python
//pseudocode
//callback_function
def name_of_callback(data: RealTimeData):
    //do something

Events = client.Trading_Data_Stream(tickers = ['ticker_1','ticker_2',,,'ticker_n'], callback = name_of_callback)
Events.start()
# tickers can include ticker, coveredwarrant, index and derivative.
Events = client.Trading_Data_Stream(tickers = ['ticker_1','ticker_2',,,'ticker_n'], callback = name_of_callback)
Events.start()
```

**RealTimeData has the following methods and attributes:**

| Data object method name | Description                                                                         |
| ----------------------- | ----------------------------------------------------------------------------------- |
| to\_dataFrame( )        | Return all data attributes instead of individual ones, stored as a Pandas DataFrame |

**RealTimeData has the following attributes:**

| Attributes             | Description                                             | Data type |
| ---------------------- | ------------------------------------------------------- | --------- |
| Ticker                 | Code name                                               | str       |
| TotalMatchVolume       | Total volume                                            | int       |
| MarketStatus           | Market status                                           | str       |
| TradingDate            | Time                                                    | str       |
| ComGroupCode           | Indicator code                                          | str       |
| Reference              | Reference value                                         | float     |
| Open                   | Open price                                              | float     |
| Close                  | Close price                                             | float     |
| High                   | High price                                              | float     |
| Low                    | Low price                                               | float     |
| Change                 | Change relative to reference value                      | float     |
| ChangePercent          | Percentage change relative to reference value           | float     |
| MatchVolume            | Matching volume                                         | int       |
| MatchValue             | Matching value                                          | float     |
| TotalMatchValue        | Total matching value                                    | float     |
| TotalBuyTradeVolume    | Total buying volume                                     | int       |
| TotalSellTradeVolume   | Total selling volume                                    | int       |
| TotalDealVolume        | Total deal volume                                       | int       |
| TotalDealValue         | Total deal value                                        | float     |
| ForeignBuyVolumeTotal  | Total foreign buy volume from the beginning of the day  | int       |
| ForeignBuyValueTotal   | Total foreign buy value from the beginning of the day   | float     |
| ForeignSellVolumeTotal | Total foreign sell volume from the beginning of the day | int       |
| ForeignSellValueTotal  | Total foreign sell value from the beginning of the day  | float     |
| Bu                     | Active buy volume                                       | int       |
| Sd                     | Active sell volume                                      | int       |

**Example of order matching data (RealTimeData):**

```python
import FiinQuantX as fq
from FiinQuantX import RealTimeData
import pandas as pd
import time

client = fq.FiinSession(
    username='Enter your username',
    password='Enter your password'
)
client.login()

tickers = ['HPG','VNINDEX','VN30F1M']

def onTickerEvent(data: RealTimeData):
    print('----------------')
    print(data.to_dataFrame())
    # data.to_dataFrame().to_csv('callback.csv', mode='a', header=True)
Events = client.Trading_Data_Stream(tickers=tickers, callback = onTickerEvent)
Events.start()

try:
    while not Events._stop: 
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt received, stopping...")
    Events.stop()
```
