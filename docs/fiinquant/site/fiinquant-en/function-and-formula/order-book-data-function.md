# Order book data function

## 7. Detailed real-time data on price steps within each order book

How to use the library after logging in. Detailed examples are provided at the end of this chapter.

```python
event = client.BidAsk(tickers = tickers, callback = callback)
```

**Paramtere**

<table><thead><tr><th>Parameter</th><th width="270.1640625">Description</th><th width="147.6328125">Data type</th><th>Required</th></tr></thead><tbody><tr><td>tickers</td><td>Code name, including stock codes, index codes, derivative codes, and covered warrant codes. These codes are written in uppercase.</td><td><p>list [str]</p><p><br></p></td><td>Yes</td></tr><tr><td>callback</td><td>This is a user-defined function for data manipulation.</td><td>function</td><td>Yes</td></tr></tbody></table>

The data receiving class is **BidAsk**, with the following two methods:

<figure><img src="/files/YAC6Nv3mqcMFLlwm4Sma" alt=""><figcaption></figcaption></figure>

**callback function**

This is a user-defined method for data manipulation, which will be passed as an argument when initializing the data receiving object. This method will have the following format:

```
//pseudocode
//callback_function
def name_of_callback(data: BidAskData):
    //do something

event = client.BidAsk(tickers = ['ticker_1','ticker_2',,,'ticker_n'], callback = name_of_callback)
event.start()
# tickers can include ticker, coveredwarrant, index and derivative.
event = client.BidAsk(tickers = ['ticker_1','ticker_2',,,'ticker_n'], callback = name_of_callback)
evente.start()
```

BidAskData has the following methods and attributes:

| BidAskData has the following attributes: | Description                                                                           |
| ---------------------------------------- | ------------------------------------------------------------------------------------- |
| to\_dataFrame( )                         | Returns all data attributes instead of individual ones, stored as a Pandas DataFrame. |

Data BidAskData has the following attributes:

<table><thead><tr><th width="209.7109375">Name</th><th width="317.7265625">Description</th><th>Data type</th></tr></thead><tbody><tr><td>ComGroupCode</td><td>Company group code</td><td>str</td></tr><tr><td>StockType</td><td>Securities type</td><td>str</td></tr><tr><td>Ticker</td><td>Code name</td><td>str</td></tr><tr><td>TradingDate</td><td>Time</td><td>str</td></tr><tr><td>Timestamp</td><td>Time (rounded to seconds)</td><td>str</td></tr><tr><td>Spread</td><td>Best1Ask - Best1Bid.</td><td>float</td></tr><tr><td>SpreadDelta</td><td>Current spread tick - Previous spread tick</td><td>float</td></tr><tr><td>DepthImbalance</td><td>TotalBidVolume / (TotalBidVolume + TotalAskVolume).</td><td>float</td></tr><tr><td>TotalBuyTradeVolume</td><td>Total buy trading volume</td><td>int</td></tr><tr><td>TotalSellTradeVolum</td><td>Total sell trading volume</td><td>int</td></tr><tr><td>TotalBidVolume</td><td>Total bid volume</td><td>int</td></tr><tr><td>TotalAskVolume</td><td>Total ask volume</td><td>int</td></tr><tr><td>Best1Bid</td><td>Bid price level 1</td><td>float</td></tr><tr><td>Best2Bid</td><td>Bid price level 2</td><td>float</td></tr><tr><td>Best3Bid</td><td>Bid price level 3</td><td>float</td></tr><tr><td>Best4Bid</td><td>Bid price level 4</td><td>float</td></tr><tr><td>Best5Bid</td><td>Bid price level 5</td><td>float</td></tr><tr><td>Best6Bid</td><td>Bid price level 6</td><td>float</td></tr><tr><td>Best7Bid</td><td>Bid price level 7</td><td>float</td></tr><tr><td>Best8Bid</td><td>Bid price level 8</td><td>float</td></tr><tr><td>Best9Bid</td><td>Bid price level 9</td><td>float</td></tr><tr><td>Best10Bid</td><td>Bid price level 10</td><td>float</td></tr><tr><td>Best1Ask</td><td>Ask price level 1</td><td>float</td></tr><tr><td>Best2Ask</td><td>Ask price level 2</td><td>float</td></tr><tr><td>Best3Ask</td><td>Ask price level 3</td><td>float</td></tr><tr><td>Best4Ask</td><td>Ask price level 4</td><td>float</td></tr><tr><td>Best5Ask</td><td>Ask price level 5</td><td>float</td></tr><tr><td>Best6Ask</td><td>Ask price level 6</td><td>float</td></tr><tr><td>Best7Ask</td><td>Ask price level 7</td><td>float</td></tr><tr><td>Best8Ask</td><td>Ask price level 8</td><td>float</td></tr><tr><td>Best9Ask</td><td>Ask price level 9</td><td>float</td></tr><tr><td>Best10Ask</td><td>Ask price level 10</td><td>float</td></tr><tr><td>Best1BidVolume</td><td>Bid volume at bid price level 1</td><td>int</td></tr><tr><td>Best2BidVolume</td><td>Bid volume at bid price level 2</td><td>int</td></tr><tr><td>Best3BidVolume</td><td>Bid volume at bid price level 3</td><td>int</td></tr><tr><td>Best4BidVolume</td><td>Bid volume at bid price level 4</td><td>int</td></tr><tr><td>Best5BidVolume</td><td>Bid volume at bid price level 5</td><td>int</td></tr><tr><td>Best6BidVolume</td><td>Bid volume at bid price level 6</td><td>int</td></tr><tr><td>Best7BidVolume</td><td>Bid volume at bid price level 7</td><td>int</td></tr><tr><td>Best8BidVolume</td><td>Bid volume at bid price level 8</td><td>int</td></tr><tr><td>Best9BidVolume</td><td>Bid volume at bid price level 9</td><td>int</td></tr><tr><td>Best10BidVolume</td><td>Bid volume at bid price level 10</td><td>int</td></tr><tr><td>Best1AskVolume</td><td>Ask volume at bid price level 1</td><td>int</td></tr><tr><td>Best2AskVolume</td><td>Ask volume at bid price level 2</td><td>int</td></tr><tr><td>Best3AskVolume</td><td>Ask volume at bid price level 3</td><td>int</td></tr><tr><td>Best4AskVolume</td><td>Ask volume at bid price level 4</td><td>int</td></tr><tr><td>Best5AskVolume</td><td>Ask volume at bid price level 5</td><td>int</td></tr><tr><td>Best6AskVolume</td><td>Ask volume at bid price level 6</td><td>int</td></tr><tr><td>Best7AskVolume</td><td>Ask volume at bid price level 7</td><td>int</td></tr><tr><td>Best8AskVolume</td><td>Ask volume at bid price level 8</td><td>int</td></tr><tr><td>Best9AskVolume</td><td>Ask volume at bid price level 9</td><td>int</td></tr><tr><td>Best10AskVolume</td><td>Ask volume at bid price level 10</td><td>int</td></tr><tr><td>BidPriceDelta1</td><td>Current best bid price tick difference from previous tick</td><td>float</td></tr><tr><td>BidPriceDelta2</td><td>Current 2nd best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta3</td><td>Current 3rd best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta4</td><td>Current 4th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta5</td><td>Current 5th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta6</td><td>Current 6th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta7</td><td>Current 7th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta8</td><td>Current 8th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta9</td><td>Current 9th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidPriceDelta10</td><td>Current 10th best bid price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta1</td><td>Current best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta2</td><td>Current 2nd best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta3</td><td>Current 3rd best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta4</td><td>Current 4th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta5</td><td>Current 5th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta6</td><td>Current 6th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta7</td><td>Current 7th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta8</td><td>Current 8th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta9</td><td>Current 9th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>AskPriceDelta10</td><td>Current 10th best ask price tick difference from previous tick.</td><td>float</td></tr><tr><td>BidVolumeDelta1</td><td>Current best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta2</td><td>Current 2nd best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta3</td><td>Current 3rd best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta4</td><td>Current 4th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta5</td><td>Current 5th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta6</td><td>Current 6th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta7</td><td>Current 7th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta8</td><td>Current 8th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta9</td><td>Current 9th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>BidVolumeDelta10</td><td>Current 10th best bid volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta1</td><td>Current best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta2</td><td>Current 2nd best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta3</td><td>Current 3rd best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta4</td><td>Current 4th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta5</td><td>Current 5th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta6</td><td>Current 6th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta7</td><td>Current 7th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta8</td><td>Current 8th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta9</td><td>Current 9th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>AskVolumeDelta10</td><td>Current 10th best ask volume tick difference from previous tick.</td><td>int</td></tr><tr><td>VWAPBid</td><td>Average price that buyers are willing to pay.</td><td>float</td></tr><tr><td>VWAPAsk</td><td>Average price that sellers are willing to pay.</td><td>float</td></tr><tr><td>VWAPBidSpread</td><td>Difference between best bid price (Best1Bid) and VWAP Bid.</td><td>float</td></tr><tr><td>VWAPAskSpread</td><td>Difference between VWAP Ask and best ask price (Best1Ask).</td><td>float</td></tr><tr><td>VWAPBidAskSpread</td><td>Difference between VWAP Ask and VWAP Bid.</td><td>float</td></tr><tr><td>OrderFlowImbalance</td><td>VWAP Bid Spread / (VWAP Bid Spread + VWAP Ask Spread).</td><td>float</td></tr></tbody></table>

**Example of Order Book Data (BidAskData):**

```
import FiinQuantX as fq
from FiinQuantX import BidAskData
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
Events = client.BidAsk(tickers=tickers, callback = onTickerEvent)
Events.start()

try:
    while not Events._stop: 
        time.sleep(1)
except KeyboardInterrupt:
    print("KeyboardInterrupt received, stopping...")
    Events.stop()
```
