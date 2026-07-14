# Function for connecting real-time and historical data

## 6. Connecting real-time and historical data

The mechanism for combining historical and real-time data works as follows:

* When the user makes the initial call, the library retrieves historical data that matches the specified timeframe.
* When the real-time parameter is set to "True", the library connects to data via WebSocket and updates it in real time. Subsequent timeframes are then aggregated from this real-time data.

{% hint style="warning" %}
**Warning:** Since subsequent timeframes are updated in real time, maintaining a stable connection will ensure the most accurate data aggregation. For real-time connections, we recommend using a wired network (LAN) and a stable internet connection.

If you need to synchronize with data from the server, users can build a mechanism to recall the function when needed to retrieve aggregated historical data from the server.
{% endhint %}

**Please note:** Due to a small delay between the server and the library, when executing code to combine real-time data, users will need to wait a moment for the data to synchronize and be accurate.

**Note:** When passing `period` in `realtime = True` mode, `period` refers to the number of historical candles. For example, in the first call with `period = 100`, it will be the 100 most recent candles, with the 100th candle being the real-time candle that is still updating. When moving to subsequent candles, the returned data will be more than 100.

```python
event = client.Fetch_Trading_Data(
    realtime = True, 
    tickers = tickers,
    fields = ['open','high','low','close','volume','bu','sd'], 
    by = by,
    callback = callback, 
    adjusted = True,
    period = 100,
    wait_for_full_timeFrame = False
)
```

**Parameters:** (Note: *`period` only exists when `from_date` is not passed, and vice versa.*)

<table><thead><tr><th>Parameter</th><th width="213.80078125">Description</th><th>Data type</th><th width="107.32421875">Default</th><th width="150.70703125">Required</th></tr></thead><tbody><tr><td>realtime</td><td>Subscribe to continuous data updates or only retrieve historical data up to the latest point (<code>True</code> for yes, <code>False</code> for no).</td><td>bool</td><td></td><td>Yes</td></tr><tr><td>tickers</td><td>Stock codes are written in uppercase.</td><td>list</td><td></td><td>Yes</td></tr><tr><td>fields</td><td>The data fields to retrieve: <code>['open','high','low','close','volume','bu','sd']</code> corresponding to Open, High, Low, Close, Volume, BU, SD.</td><td>list</td><td></td><td>Yes</td></tr><tr><td>adjusted</td><td>Adjusted or unadjusted price (<code>True</code> for adjusted, <code>False</code> for unadjusted).</td><td>bool</td><td>True</td><td>No</td></tr><tr><td>callback</td><td>This is a user-defined function for data manipulation.</td><td>function</td><td></td><td>Yes</td></tr><tr><td>by</td><td>Time unit (1m, 5m, 15m, 30m, 1h, 2h, 4h, 1d).</td><td>str</td><td>1M</td><td>No</td></tr><tr><td>period</td><td>Number of most recent historical candles to retrieve.</td><td>int</td><td></td><td>No</td></tr><tr><td>from_date</td><td>Earliest timestamp for data retrieval.</td><td>str</td><td>datetime</td><td></td></tr><tr><td>to_date</td><td>Latest timestamp for data retrieval.</td><td>str</td><td>datetime</td><td>datetime.now()</td></tr><tr><td>wait_for_full_timeFrame</td><td>Wait until the candle closes before calling the callback or not (<code>True</code> for waiting until the candle closes, <code>False</code> for continuous updates).</td><td>bool</td><td>False.</td><td>No</td></tr></tbody></table>

**callback function**

A user-defined method for data manipulation, which will be passed as an argument when initializing the data receiving object. This method will have the following format:

```python
### pseudocode

## callback_function
def name_of_callback(data: BarDataUpdate):
    ## do something

event = client.Fetch_Trading_Data(
    realtime=True,
    tickers=tickers,
    fields = ['open','high','low','close','volume','bu','sd'], 
    adjusted=True,
    callback=name_of_callback,
    by='1M', 
    from_date='2024-11-28 09:00'
)

event.get_data()
```

Stock data has the following attributes:

| Attributes | Description         | Data type |
| ---------- | ------------------- | --------- |
| ticker     | Code name           | str       |
| timestamp  | Trading time        | int       |
| open       | Open price          | float     |
| low        | Lowest price        | float     |
| high       | Highest price       | float     |
| close      | Close price         | float     |
| volume     | Trading volume      | int       |
| bu         | Buy volume          | int       |
| sd         | Sell volume         | int       |
| fb         | Foreign sell volume | int       |
| fs         | Foreign buy voulume | int       |
| fn         | Net buy/ sell value | int       |

**Example**

* **Case 1:** Using `from_date`

Copy

```python
import time
import pandas as pd
import FiinQuantX as fq
from FiinQuantX import BarDataUpdate

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(username=username, password=password).login()

tickers = ['HPG', 'SSI', 'VNM', 'VIC', 'VRE']

def onUpdate(data: BarDataUpdate):
    print(data.to_dataFrame())
    print('-------------Callback-------------')
    
event = client.Fetch_Trading_Data(
    realtime = True,
    tickers = tickers,    
    fields = ['open','high','low','close','volume','bu','fn'],
    by = '1m', 
    callback = onUpdate, 
    from_date='2024-11-28 09:00',
    wait_for_full_timeFrame = False
)

event.get_data()

try:
    while not event._stop:
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt received, stopping...")
    event.stop()
```

* Case 2: Using `period`

Copy

```python
import time
import pandas as pd
import FiinQuantX as fq
from FiinQuantX import BarDataUpdate

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = fq.FiinSession(username=username, password=password).login()

tickers = ['HPG', 'SSI', 'VN30', 'VN30F1M', 'VRE']

def onUpdate(data: BarDataUpdate):
    print(data.to_dataFrame())
    print('-------------Callback-------------')
    
event = client.Fetch_Trading_Data(
    realtime = True,
    tickers = tickers,    
    fields = ['open', 'high', 'low', 'close', 'volume', 'bu'],
    by = '1m', 
    period = 10,
    callback = onUpdate, 
    wait_for_full_timeFrame=False
)

event.get_data()
time.sleep(3600)
event.stop()
#Ví dụ chạy 1 giờ rồi ngưng.
```

| Method      | Description                                                                                                 |
| ----------- | ----------------------------------------------------------------------------------------------------------- |
| get\_data() | Get the latest data if `realtime = False`, or start the connection and receive data with `realtime = True`. |
| stop( )     | Stop connecting                                                                                             |
