# List of technical analysis indicators

## **1. Trend Indicators**&#x20;

### 1.1. **EMA (Exponential Moving Average)**

> **EMA** is a moving average line calculated with a weighting system that assigns greater importance to more recent price data. EMA reacts faster to price changes, helping investors grasp market trends promptly.

```python
def ema(column: pandas.core.series.Series, window: int)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="221.03125">Meaning</th><th width="173.90234375">Data type</th><th>Default</th></tr></thead><tbody><tr><td>column</td><td>The data column (series) contains the values for calculating EMA.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the EMA calculation.</td><td>int</td><td></td></tr></tbody></table>

Example

```python
fi = client.FiinIndicator()
df['ema_5'] = fi.ema(df['close'], window = 5)
print(df)
```

### **1.2. SMA (Simple Moving Average)**

> SMA is a simple moving average, an indicator calculated by taking the arithmetic mean of prices over a specified period.

```python
def sma(column: pandas.core.series.Series, window: int)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="221.03125">Meaning</th><th width="173.90234375">Data type</th><th>Default</th></tr></thead><tbody><tr><td>column</td><td>The data column (series) contains the values for calculating SMA.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the SMA calculation.</td><td>int</td><td></td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['sma_5'] = fi.sma(df['close'], window = 5)
print(df)
```

### **1.3. WMA (Weighted Moving Average)**

> WMA is a **weighted linear moving average**. This indicator is more sensitive and closely tracks market price fluctuations. WMA assigns different weights to each value in the data series, with the highest weights given to the most recent data and gradually decreasing for older values. This characteristic makes the WMA line more sensitive and "smoother" compared to SMA or EMA moving averages.

```python
def wma(column: pandas.core.series.Series, window: int)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="221.03125">Meaning</th><th width="173.90234375">Data type</th><th>Default</th></tr></thead><tbody><tr><td>column</td><td>The data column (series) contains the values for calculating WMA.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the WMA calculation.</td><td>int</td><td></td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['wma'] = fi.wma(df['close'], window = 14)
print(df)
```

### **1.4. MACD (Moving Average Convergence Divergence)**

> MACD is one of the most widely used technical analysis tools by traders. It helps measure the momentum, direction, and strength of a price trend.
>
> **Structure:**
>
> * **MACD Line:** The difference between a short-term EMA (typically 12 days) and a long-term EMA (typically 26 days).
> * **Signal Line:** The EMA of the MACD line (typically 9 days).
> * **MACD Histogram:** The difference between the MACD line and the Signal line.

```python
def macd(column: pandas.core.series.Series, window_slow: int = 26, window_fast: int = 12)

def macd_signal(column: pandas.core.series.Series, window_slow: int = 26, window_fast: int = 12, window_sign: int = 9)

def macd_diff(column: pandas.core.series.Series, window_slow: int = 26, window_fast: int = 12, window_sign: int = 9)
```

**Parameter**

| Paramter     | Description                                                                | Data type     | Default |
| ------------ | -------------------------------------------------------------------------- | ------------- | ------- |
| column       | The data column (series) containing the values for calculating MACD.       | pandas.Series |         |
| window\_slow | Number of data points used for the long-term EMA in the MACD calculation.  | int           | 26      |
| window\_fast | Number of data points used for the short-term EMA in the MACD calculation. | int           | 12      |
| window\_sign | Number of data points used for the EMA in the MACD Signal calculation.     | int           | 9       |

Example:

```python
fi = client.FiinIndicator()
df['macd'] = fi.macd(df['close'], window_fast=12, window_slow=26)
df['macd_signal'] = fi.macd_signal(df['close'], window_fast=12, window_slow=26, window_sign=9)
df['macd_diff'] = fi.macd_diff(df['close'], window_fast=12, window_slow=26, window_sign=9)
print(df)
```

### **1.5. ADX (ADXIndicator)**

> ADX is an oscillating indicator tool used to determine the strength of a trend. It's commonly used to identify whether a market is trending sideways (sideway market) or has begun a new trend. Initially, this indicator was widely used in commodity markets but has since expanded to many other financial markets, such as stocks, forex, and cryptocurrencies.

```python
def adx(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14)

def adx_neg(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14)

def adx_pos(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14)
```

**Tham số**

| Paramter | Meaning                                                                  | Data type     | Default |
| -------- | ------------------------------------------------------------------------ | ------------- | ------- |
| low      | The data column containing the lowest price values for ADX calculation.  | pandas.Series |         |
| high     | The data column containing the highest price values for ADX calculation. | pandas.Series |         |
| close    | The data column containing the closing price values for ADX calculation. | pandas.Series |         |
| window   | Number of data points used in the ADX calculation.                       | int           | 14      |

Example:

```python
fi = client.FiinIndicator()
df['adx'] = fi.adx(df['high'], df['low'], df['close'], window=14)
df['adx_neg'] = fi.adx_neg(df['high'], df['low'], df['close'], window=14)
df['adx_pos'] = fi.adx_pos(df['high'], df['low'], df['close'], window=14)
print(df)
```

### **1.6. PSAR (Parabolic Stop and Reverse)**

PSAR is a technical indicator developed by J. Welles Wilder Jr., used to determine price trends and reversal points in trading. PSAR lies below the price during an uptrend and above the price during a downtrend, helping traders identify support or resistance levels. When the price crosses PSAR, the trend may reverse. This indicator is easy to use, especially effective in strongly trending markets, but can generate noisy signals in sideways markets.

```python
def psar(self, high: pd.Series, low: pd.Series, close: pd.Series, step: float = 0.02, max_step: float = 0.2)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="258.390625">Description</th><th>Data type</th><th>Default</th></tr></thead><tbody><tr><td>high</td><td>Column containing highest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing lowest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values.</td><td>pandas.Series</td><td></td></tr><tr><td>step</td><td>Initial Acceleration Factor (AF) in the calculation process. A smaller step means PSAR reacts slower to price changes, suitable for less volatile markets. A larger step means PSAR is more sensitive, quickly catching changes but potentially generating noisy signals.</td><td>float</td><td>0.02</td></tr><tr><td>max_step</td><td>Maximum value the Acceleration Factor (AF) can reach.</td><td>float</td><td>0.2</td></tr></tbody></table>

Example:

<pre class="language-python"><code class="lang-python">fi = client.FiinIndicator()
<strong>df['psar'] = fi.psar(df['high'], df['low'], df['close'], step=0.02, max_step=0.2)
</strong><strong>print(df)
</strong></code></pre>

### **1.7. Ichimoku (Ichimoku Kinko Hyo)**

Ichimoku is a technical indicator developed by Goichi Hosoda. It helps assess trends, support, resistance levels, and provides buy/sell signals within a single chart. The indicator consists of five main components: Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, and Chikou Span, forming a "cloud" (Kumo) that reflects market dynamics. Ichimoku is particularly effective in clearly trending markets, assisting traders in making decisions based on price equilibrium.

```python
def ichimoku_a(self, high: pd.Series, low: pd.Series, close: pd.Series, window1: int = 9, window2: int = 26, window3: int = 52) -> pd.Series: ...
def ichimoku_b(self, high: pd.Series, low: pd.Series, close: pd.Series, window1: int = 9, window2: int = 26, window3: int = 52) -> pd.Series: ...
def ichimoku_base_line(self, high: pd.Series, low: pd.Series, close: pd.Series, window1: int = 9, window2: int = 26, window3: int = 52) -> pd.Series: ...
def ichimoku_conversion_line(self, high: pd.Series, low: pd.Series, close: pd.Series, window1: int = 9, window2: int = 26, window3: int = 52) -> pd.Series: ...
def ichimoku_lagging_line(self, high: pd.Series, low: pd.Series, close: pd.Series,
    window1: int = 9, window2: int = 26, window3: int = 52) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="248.88671875">Description</th><th>Data type</th><th width="111.19921875">Default</th></tr></thead><tbody><tr><td>high</td><td>Column containing highest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing lowest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price data.</td><td>pandas.Series</td><td></td></tr><tr><td>window1</td><td>Number of data points used for the Conversion Line (Tenkan-sen).</td><td>int</td><td>9</td></tr><tr><td>window2</td><td>Number of data points used for the Base Line (Kijun-sen) and for translating lines like Chikou Span and Senkou Span A/B.</td><td>int</td><td>26</td></tr><tr><td>window3</td><td>Number of data points used for the Senkou Span B line.</td><td>int</td><td>52</td></tr></tbody></table>

Example

```python
fi = client.FiinIndicator()
df['senkou_span_a'] = fi.ichimoku_a(df['high'], df['low'], df['close'], window1 = 9, window2 = 26, window3 = 52)
df['senkou_span_b'] = fi.ichimoku_b(df['high'], df['low'], df['close'], window1 = 9, window2 = 26, window3 = 52)
df['kijun_sen'] = fi.ichimoku_base_line(df['high'], df['low'], df['close'], window1 = 9, window2 = 26, window3 = 52) 
df['tenkan_sen'] = fi.ichimoku_conversion_line(df['high'], df['low'], df['close'], window1 = 9, window2 = 26, window3 = 52)
print(df)
```

### **1.8. CCI (Commodity Channel Index)**

CCI is a technical indicator developed by Donald Lambert used to measure the deviation of price from its average over a period, helping to identify overbought or oversold conditions. When CCI goes above 100, the price might be overbought, and when below -100, the price might be oversold. This indicator is suitable for detecting new trends or signaling potential reversals.

```python
def cci(self, high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20, constant: float = 0.015) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="221.22265625">Description</th><th>Data type</th><th width="122.2109375">Default</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used for the SMA and Mean Deviation.</td><td>int</td><td>20</td></tr><tr><td>constant</td><td>Constant for normalization to ensure CCI values oscillate within a defined range.</td><td>float</td><td>0.015</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['cci'] = fi.cci(df['high'], df['low'], df['close'], window = 20, constant = 0.015)
print(df)
```

### **1.9. Aroon**

Aroon is a technical indicator developed by Tushar Chande, used to measure trend strength and identify the beginning or end of a trend. The indicator consists of two main components: Aroon-Up (tracking the highest high) and Aroon-Down (tracking the lowest low) over a specified period. Values range from 0 to 100, with high values indicating a strong trend and low values indicating a weakening trend. Aroon is particularly useful for detecting accumulation phases or reversals in the market.

```python
def aroon(self, high: pd.Series, low: pd.Series, window: int = 25) -> pd.Series: ...
def aroon_up(self, high: pd.Series, low: pd.Series, window: int = 25) -> pd.Series: ... 
def aroon_down(self, high: pd.Series, low: pd.Series, window: int = 25) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="237.87890625">Description</th><th width="184">Data type</th><th width="126.984375">Default value</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used for the SMA and Mean Deviation.</td><td>int</td><td>25</td></tr></tbody></table>

Example:&#x20;

```python
fi = client.FiinIndicator()
df['aroon'] = fi.aroon(df['high'], df['low'], window: int = 25)
df['aroon_up'] = fi.aroon_up(df['high'], df['low'], window: int = 25)
df['aroon_down'] = fi.aroon_down(df['high'], df['low'], window: int = 25)
print(df)
```

## 2. Momentum Indicators (Chỉ báo động lượng)

### **2.1. RSI (Relative Strength Index)**

> RSI is an indicator that measures the speed and magnitude of recent price changes to assess whether an asset is **overbought** or **oversold**.
>
> RSI is calculated based on closing prices over a specific period (typically 14 days).
>
> This index fluctuates between 0 and 100.
>
> * **RSI above 70**: This is the overbought zone; the asset may have risen too quickly and could be due for a downward correction.
> * **RSI below 30**: This is the oversold zone; the asset may have fallen too deeply and could be due for a rebound.

```python
def rsi(column: pandas.core.series.Series, window: int = 14)
```

**Parameter**

| Parameter | Description                                                | Data type     | Default value |
| --------- | ---------------------------------------------------------- | ------------- | ------------- |
| column    | Column (series) containing the values for calculating RSI. | pandas.Series |               |
| window    | Number of data points used in the RSI calculation.         | int           | 14            |

Example:

```python
fi = client.FiinIndicator()
df['rsi'] = fi.rsi(df['close'], window=14)
print(df)
```

### **2.2. Stochastic**

> The Stochastic Oscillator is an effective technical analysis tool that helps assess price momentum and potential reversals, identifying potential buy/sell zones in the market.
>
> **Structure:**
>
> * **%K line**: This line compares the current closing price of the security with its highest and lowest price range over a specified period. Above 80 indicates the security might be overbought, with a potential for price correction downwards. Below 20 suggests the security might be oversold, with a potential for price recovery.
> * **%D line**: This is the Simple Moving Average (SMA) of the %K line, helping to smooth out short-term fluctuations.

> Both %K and %D oscillate between 0 and 100.

```python
def stoch(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14, smooth_window: int = 3)
```

```python

def stoch_signal(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14, smooth_window: int = 3)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="212.87109375">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>low</td><td>Column containing the lowest price values for Stochastic calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Column containing the highest price values for Stochastic calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values for Stochastic calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the Stochastic calculation.</td><td>int</td><td>14</td></tr><tr><td>smooth_window</td><td>Number of data points used in the Stochastic Signal calculation by taking the SMA of Stochastic.</td><td>int</td><td>3</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['stoch'] = fi.stoch(df['high'], df['low'], df['close'], window=14)
df['stoch_signal'] = fi.stoch_signal(df['high'], df['low'], df['close'], window=14, smooth_window=3)
print(df)
```

## 3. Volatility Indicators

### **3.1. Bollinger Bands**

> Bollinger Bands is a technical analysis tool developed by John Bollinger in the 1980s. Bollinger Bands help measure price volatility and identify potential high/low price levels within a trend.
>
> **Structure:**
>
> * **Centerline**: A moving average (typically a 20-day SMA) of the price.
> * **Upper Band**: A specified number of standard deviations (typically 2) calculated from the centerline, added to the centerline's value.
> * **Lower Band**: A specified number of standard deviations (typically 2) calculated from the centerline, subtracted from the centerline's value.

```python
def bollinger_hband(column: pandas.core.series.Series, window: int = 20, window_dev: int = 2)

def bollinger_lband(column: pandas.core.series.Series, window: int = 20, window_dev: int = 2)
```

**Parameter**

<table><thead><tr><th width="144.625">Parameter</th><th width="237.2578125">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>column</td><td>Column containing the values for calculating Bollinger Bands.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the Bollinger Bands calculation.</td><td>int</td><td>20</td></tr><tr><td>window_dev</td><td>Number of standard deviations used to calculate the distance of Bollinger Bands.</td><td>int</td><td>2</td></tr></tbody></table>

Example

<pre class="language-python"><code class="lang-python">fi = client.FiinIndicator()
df['bollinger_hband'] = fi.bollinger_hband(df['close'], window=20, window_dev=2)
<strong>df['bollinger_lband'] = fi.bollinger_lband(df['close'], window=20, window_dev=2)
</strong>print(df)
</code></pre>

### **3.2. Supertrend**

> Supertrend (super trend) is a technical analysis tool developed by investor Olivier Seban in 2010. Supertrend uses a combination of factors such as price, ATR (Average True Range), and the current trend to identify the main market trend and potential reversal points.

```python
def supertrend(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14, multiplier: float = 3.0)


def supertrend_hband(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14, multiplier: float = 3.0)


def supertrend_lband(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14, multiplier: float = 3.0)
```

**Parameter**

<table><thead><tr><th width="139.5390625">Parameter</th><th width="231.984375">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values for Supertrend calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values for Supertrend calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values for Supertrend calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the Supertrend calculation.</td><td>int</td><td>14</td></tr><tr><td>multiplier</td><td>Multiplier used to adjust the width of the Supertrend indicator relative to the price level.</td><td>float</td><td>3.0</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['supertrend'] = fi.supertrend(df['high'], df['low'], df['close'], window=14)
df['supertrend_hband'] = fi.supertrend_hband(df['high'], df['low'], df['close'], window=14)
df['supertrend_lband'] = fi.supertrend_lband(df['high'], df['low'], df['close'], window=14)
print(df)
```

### **3.3. ATR (Average True Range)**

> ATR stands for Average True Range. This indicator measures price volatility over a specific period.
>
> The indicator was introduced in J. Welles Wilder Jr.'s 1978 book, "New Concepts in Technical Trading Systems." Through this indicator, investors can predict future price fluctuations. This provides investors with a basis for setting appropriate stop-loss and take-profit points.

```python
def atr(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, window: int = 14)
```

**Parameter**

<table><thead><tr><th width="138.85546875">Parameter</th><th width="226.47265625">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values for ATR calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values for ATR calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values for ATR calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the ATR calculation.</td><td>int</td><td>14</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['atr'] = fi.atr(df['high'], df['low'], df['close'], window=14)
print(df)
```

## 4. Volume Indicators&#x20;

### **4.1. MFI (Money Flow Index)**

> MFI is an indicator reflecting the money flow strength of a stock over a specified period, analyzed based on trading volume. The period is considered daily, weekly, or monthly, and typically calculated over 14 periods.

```python
def mfi(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, volume: pandas.core.series.Series, window: int = 14)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="238.703125">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values for MFI calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values for MFI calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values for MFI calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>volume</td><td>Column containing trading volume values for MFI calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the MFI calculation.</td><td>int</td><td>14</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['mfi'] = fi.mfi(df['high'], df['low'], df['close'], df['volume'], window=14)
print(df)
```

### **4.2. OBV (On Balance Volume)**

> OBV is a volume indicator that measures cumulative trading volume across sessions, thereby showing whether a stock is trending towards being bought or sold. If today's session is an up day, the volume is added to the OBV indicator. Conversely, volume is subtracted when today is a down trading session.

```python
def obv(column: pandas.core.series.Series, volume: pandas.core.series.Series)
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="240.19921875">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>column</td><td>Column (series) containing price values for OBV calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>volume</td><td>Column containing trading volume values for OBV calculation.</td><td>pandas.Series</td><td></td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['obv'] = fi.obv(df['close'], df['volume'])
print(df)
```

### **4.3. VWAP (Volume Weighted Adjusted Price)**

> VWAP stands for Volume Weighted Average Price, the average price of a stock calculated by its total trading volume. VWAP is used to determine a stock's average price over a period.
>
> The volume-weighted average price helps compare a stock's current price to a benchmark, making it easier for investors to decide when to enter and exit the market. Additionally, VWAP can assist investors in determining their investment approach for a stock and executing appropriate trading strategies at the right time.

```python
def vwap(high: pandas.core.series.Series, low: pandas.core.series.Series, close: pandas.core.series.Series, volume: pandas.core.series.Series, window: int = 14)
```

**Parameter**

<table><thead><tr><th width="139.99609375">Parameter</th><th width="248.203125">Description</th><th>Data type</th><th>Default value</th></tr></thead><tbody><tr><td>high</td><td>Column containing the highest price values for VWAP calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Column containing the lowest price values for VWAP calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Column containing closing price values for VWAP calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>volume</td><td>Column containing trading volume values for VWAP calculation.</td><td>pandas.Series</td><td></td></tr><tr><td>window</td><td>Number of data points used in the VWAP calculation.</td><td>int</td><td>14</td></tr></tbody></table>

Example:&#x20;

```python
fi = client.FiinIndicator()
df['vwap'] = fi.vwap(df['high'], df['low'], df['close'], df['volume'], window=14)
print(df)
```

## 5. Smart Money Concepts

### **5.1. Fair Value Gap (FVG)**

FVG is a price range on a chart that has not been filled, appearing due to an imbalance between supply and demand. If the current candle is bullish, FVG appears when the high of the preceding candle is lower than the low of the following candle. If the current candle is bearish, FVG appears when the low of the preceding candle is higher than the high of the following candle.

```python
def fvg(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, join_consecutive: bool = True) -> pd.Series: ...
    
def fvg_top(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, join_consecutive: bool = True) -> pd.Series: ...
    
def fvg_bottom(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, join_consecutive: bool = True) -> pd.Series: ...
    
def fvg_mitigatedIndex(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, join_consecutive: bool = True) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="254.828125">Description</th><th>Data type</th><th width="106.34375">Default value</th></tr></thead><tbody><tr><td>open</td><td>Open price column.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Highest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Lowest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td> Close price column.</td><td>pandas.Series</td><td></td></tr><tr><td>join_consecutive</td><td>If there are multiple consecutive FVG (Fair Value Gap) ranges, they will be merged into one, using the highest high as the top and the lowest low as the bottom.</td><td>bool</td><td>True</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['fvg'] = fi.fvg(df['open'],df['high'], df['low'], df['close'],join_consecutive=True)
print(df)
```

### **5.2. Swing Highs and Lows**

Swing high occurs when the current candle's highest price is the highest within a defined period before and after it.

Swing low occurs when the current candle's lowest price is the lowest within the same period.

```python
def swing_HL(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, swing_length: int = 50) -> pd.Series: ...
    
def swing_level(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, swing_length: int = 50)) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="257.54296875">Description</th><th>Data type</th><th width="115.0625">Default value</th></tr></thead><tbody><tr><td>open</td><td>Open price column.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Highest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Lowest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Close price column.</td><td>pandas.Series</td><td></td></tr><tr><td>swing_length</td><td>Number of candles to consider before and after to determine a swing high or swing low.</td><td>int</td><td>50</td></tr></tbody></table>

Example:

```python
fi = client.FiinIndicator()
df['swing_HL'] = fi.swing_HL(df['open'],df['high'], df['low'], df['close'], swing_length = 50)
print(df)
```

### **5.3. Break of Structure (BOS) & Change of Character (CHoCH)**

**BOS (Break of Structure)**: When the price breaks the previous trend structure (either uptrend or downtrend), it indicates a shift in market momentum.

**ChoCH (Change of Character)**: A crucial indicator showing a trend reversal. ChoCH occurs when a downtrend changes to an uptrend or vice versa.

```python
def break_of_structure(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, close_break: bool = True, swing_length: int = 50) -> pd.Series: ...
    
def chage_of_charactor(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, close_break: bool = True, swing_length: int = 50) -> pd.Series: ...
    
def bos_choch_level(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, close_break: bool = True, swing_length: int = 50) -> pd.Series: ...
    
def broken_index(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, close_break: bool = True, swing_length: int = 50) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th width="152.88671875">Parameter</th><th width="255.12890625">Description</th><th>Data type</th><th width="122.75390625">Default </th></tr></thead><tbody><tr><td>open</td><td>Open price column.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Highest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Lowest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Close price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close_break</td><td>If True, confirmation is based on the candle's closing price. If False, confirmation is based on the candle's high/low.</td><td>bool</td><td>True</td></tr><tr><td>swing_length</td><td>Number of candles to consider before and after to determine a swing high or swing low.</td><td>int</td><td>50</td></tr></tbody></table>

Example:

<pre class="language-python"><code class="lang-python">fi = client.FiinIndicator()
df['break_of_structure'] = fi.break_of_structure(df['open'],df['high'], df['low'],df['close'],swing_length=50)
<strong>df['chage_of_charactor'] = fi.chage_of_charactor(df['open'],df['high'], df['low'],df['close'])
</strong>print(df)
</code></pre>

### **5.4. Order Blocks**

An area where large institutions have placed trades, creating strong price pushes. When the price returns to the OB (Order Block) zone, this is often a potential entry point.

```python
def ob(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
    
def ob_top(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
    
def ob_bottom(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
    
def ob_volume(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
    
def ob_mitigated_index(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
    
def ob_percetage(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, close_mitigation: bool = False, swing_length: int = 50) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th>Parameter</th><th width="212.4765625">Description</th><th>Data type</th><th>Default</th></tr></thead><tbody><tr><td>open</td><td>Open price column.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Highest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Lowest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Close price column.</td><td>pandas.Series</td><td></td></tr><tr><td>volume</td><td>Volume column.</td><td>pandas.Series</td><td></td></tr><tr><td>close_mitigation</td><td>If True, confirmation is based on the candle's closing price. If False, confirmation is based on the candle's high/low.</td><td>bool</td><td>False</td></tr><tr><td>swing_length</td><td>Number of candles to consider.</td><td>int</td><td>50</td></tr></tbody></table>

Example:

```python
fi = client.Indicator()
df['ob'] = fi.ob(df['open'],df['high'], df['low'],df['close'],df['volume'], close_mitigation = False, swing_length = 40)
df['ob_volume'] = fi.ob_volume(df['open'],df['high'], df['low'],df['close'],df['volume'])
print(df)
```

### **5.5. Liquidity**

Liquidity appears when there are multiple highs or multiple lows within a small range, indicating an accumulation of orders in that area.

```python
def liquidity(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, range_percent: float = 0.01, swing_length: int = 50) -> pd.Series: ...
    
def liquidity_level(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, range_percent: float = 0.01, swing_length: int = 50) -> pd.Series: ...
    
def liquidity_end(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, range_percent: float = 0.01, swing_length: int = 50) -> pd.Series: ...
    
def liquidity_swept(self, open: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, range_percent: float = 0.01, swing_length: int = 50) -> pd.Series: ...
```

**Parameter**

<table><thead><tr><th width="145.13671875">Parameter</th><th width="257.08984375">Description</th><th>Data type</th><th width="115.78515625">Default value</th></tr></thead><tbody><tr><td>open</td><td>Open price column.</td><td>pandas.Series</td><td></td></tr><tr><td>high</td><td>Highest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>low</td><td>Lowest price column.</td><td>pandas.Series</td><td></td></tr><tr><td>close</td><td>Close price column.</td><td>pandas.Series</td><td></td></tr><tr><td>range_percent</td><td>Percentage of the price range used to determine liquidity.</td><td>float</td><td>0.01</td></tr><tr><td>swing_length</td><td>Number of candles to consider before and after to determine a swing high or swing low.</td><td>int</td><td>50</td></tr></tbody></table>

Example:

```python
// Some codepy

fi = client.FiinIndicator()
df['liquidity'] = fi.liquidity(df['open'],df['high'], df['low'],df['close'])
print(df)
```
