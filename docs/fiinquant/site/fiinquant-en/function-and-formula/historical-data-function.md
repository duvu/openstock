# Historical data function

## 5. Get available (historical) data

How to use the library after logging in. Detailed examples are provided at the end of this chapter.

```python
data = client.Fetch_Trading_Data(
    realtime = False, 
    tickers = tickers,
    fields = ['open', 'high', 'low', 'close', 'volume', 'bu','sd'], 
    adjusted = True,
    by = by,
    period = 100
).get_data()
```

**Parameters:** (Note: *'period' only exists when 'from\_date' is not passed, and vice versa*). You must choose one of these two methods of passing data.

| Name       | Description                                                                                                                             | Data type | Default  | Required       |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------- | -------- | -------------- |
| realtime   | Whether to subscribe to continuously updated data or only call historical data up to the latest point (True for yes, False for no).     | bool      |          | Yes            |
| tickers    | All caps stock codes.                                                                                                                   | list      |          | Yes            |
| fields     | The data fields to retrieve: `['open','high','low','close','volume','bu','sd']`corresponding to Open, High, Low, Close, Volume, BU, SD. | list      |          | Yes            |
| adjusted   | Adjusted or unadjusted price (True for adjusted, False for unadjusted)                                                                  | bool      | True     | No             |
| by         | Time unit (1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d)                                                                                            | str       | 1M       | No             |
| period     | Number of most recent historical candles to retrieve                                                                                    | int       |          | No             |
| from\_date | Earliest timestamp for data retrieval.                                                                                                  | str       | datetime |                |
| to\_date   | Latest timestamp for data retrieval.                                                                                                    | str       | datetime | datetime.now() |
|            |                                                                                                                                         |           |          | No             |

The data retrieval class is **Fetch\_Trading\_Data**, with the following two methods:

| Method name | Description                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| get\_data() | Get the latest data if `realtime = False`, or start the connection and receive data with `realtime = True`. |

```python
### pseudocode
event = client.Fetch_Trading_Data(
    realtime=False,
    tickers=tickers,
    fields=['open', 'high', 'low', 'close', 'volume', 'bu','sd'], 
    adjusted=True,
    by='1m', 
    from_date='2024-11-28 09:00'
)

data=event.get_data()
print(data)
```

Data has the following attributes:

| Attributes | Description         | Data type |
| ---------- | ------------------- | --------- |
| ticker     | Code name           | str       |
| timestamp  | Trading time        | int       |
| open       | Open price          | float     |
| low        | Lowest price        | float     |
| high       | Highest price       | float     |
| close      | Close price         | float     |
| volume     | Trading volume      | int       |
| bu         | Active buy volume   | int       |
| sd         | Active sell volume  | int       |
| fb         | Foreign buy value   | int       |
| fs         | Foreign sell value  | int       |
| fn         | Net buy/ sell value | int       |

* Example

```python
import pandas as pd
import FiinQuantX as fq
from FiinQuantX import BarDataUpdate

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(username=username, password=password).login()

tickers = ['HPG', 'SSI', 'VN30F1M', 'UPCOMINDEX']
    
data = client.Fetch_Trading_Data(
    realtime = False,
    tickers = tickers,    
    fields = ['open', 'high', 'low', 'close', 'volume', 'bu', 'sd', 'fb', 'fs', 'fn'],
    adjusted=True,
    by = '1m', 
    from_date='2024-11-28 09:00',
).get_data()

print(data)
```
