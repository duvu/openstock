# AI/ML model

### AI model for analyzing historical stock prices

{% hint style="info" %}
Use LLM models with FiinQuant data to assist in finding insights as required by the user.
{% endhint %}

```python
import requests
import tqdm
from FiinQuantX import FiinSession
from bs4 import BeautifulSoup
import google.generativeai as genai
import re
import numpy as np
import pandas as pd
import os


GOOGLE_GEMINI_API_KEY = os.getenv('GOOGLE_GEMINI_API_KEY')
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


```

```python
client = FiinSession('USERNAME', 'PASSWORD').login()
VCB_data = client.Fetch_Trading_Data(
    tickers=['VCB'],
    fields=['close'],
    realtime=False,
    adjusted=True,
    by='1d', 
    from_date='2020-01-01',
    to_date='2025-01-29').get_data()
```

```python
prompt = None
prompt = (
    "You are a helpful assistant that can provide meaningful information about the stock market from the data given by the user.\n"
    "The data given by the user is a pandas dataframe with the following columns: 'Ticker', 'Date', 'Close'.\n"
    "You need to provide a summary of the data and the trends of the stock market.\n"
    "You need to find the percentage of the stock price change in the last 10 days.\n"
    "Here is the data:\n"
)
prompt += VCB_data.to_string()
```

```python
response = model.generate_content(prompt)
print(response.text)
```

Output:&#x20;

```markdown
Here's a summary of the provided stock market data for VCB, along with an analysis of trends and the 10-day percentage change:
Data Summary:
The dataset contains daily closing prices ('Close') for VCB stock from January 25, 2021, to January 24, 2025. The data shows significant fluctuations in the stock price over this period.
Trend Analysis:
A visual representation (like a line chart) would provide the clearest picture of the trends, but based on the data, we can infer the following:
Long-Term Trend: There's a general upward trend in the price of VCB from 2021 to 2025. However, there are periods of both significant growth and substantial decline within that long term trend.
Volatility: The stock is demonstrably volatile, experiencing both sharp increases and decreases within short timeframes. Significant price swings are visible throughout the dataset.
Seasonal Effects: A more detailed analysis might reveal seasonal patterns in VCB's price movements, but that is beyond the scope of this basic summary.
10-Day Percentage Change:
To calculate the 10-day percentage change, we need the closing prices for the last 10 days of the dataset. These are:
Day -10: 92900.00
Day -9: 92500.00
Day -8: 93000.00
Day -7: 92500.00
Day -6: 92000.00
Day -5: 91000.00
Day -4: 92000.00
Day -3: 91200.00
Day -2: 91000.00
Day -1: 88500.00
Day 0: 89800.00
The calculation is as follows:
Find the difference: 89800.00 - 92900.00 = -3100.00
Calculate the percentage change: (-3100.00 / 92900.00) * 100% = -3.338%
Therefore, the VCB stock price experienced an approximate -3.34% change over the last 10 days. Note that this calculation uses the simple percentage change. More sophisticated calculations could be used to smooth this value.
Further Analysis:
For a more comprehensive understanding of VCB's performance, additional data analysis is recommended including:
Moving Averages: Calculate moving averages (e.g., 50-day, 200-day) to identify longer-term trends and smoother price movements.
Statistical Measures: Calculate metrics like standard deviation to quantify volatility.
Correlation Analysis: Analyze the correlation of VCB's price with other market indices or relevant economic indicators.
Visualizations: Create charts (line charts, candlestick charts) to visualize trends and patterns.
This expanded analysis would offer a richer picture of the stock's historical performance and potential future behavior.
```

## Machine learning model for stock price prediction

Retrieve stock data from the FiinQuant library

<pre class="language-python"><code class="lang-python">import pandas as pd
from FiinQuantX import FiinSession
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import numpy as np
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor
username = 'USERNAME'
password = 'PASSWORD'
client = FiinSession(
    username=username,
    password=password
).login()
<strong>VCB_data = client.Fetch_Trading_Data(
</strong>    tickers='VCB',
    fields=['open','high','low','close','volume'],
    adjusted=True,
    period=10,
    realtime=False,
    by='1m',
).get_data()
</code></pre>

### 1. Linear Regression&#x20;

{% hint style="info" %}
**Linear Regression**

* **Main idea**: The model predicts stock prices by finding the best-fit line for historical data. The general formula is y=w0​+w1​x1​+w2​x2​+...+wn​xn​+ϵ, where y is the stock price, and xi​ are influencing factors like opening price, trading volume, etc.
* **Advantages**: It's simple, easy to understand, and calculations are fast.
* **Disadvantages**: It assumes a linear relationship between variables, making it difficult to capture the non-linearity of stock prices.
  {% endhint %}

**Prepare and run the model**

```python
# Convert Date column to datetime
VCB_data['Date'] = pd.to_datetime(VCB_data['timestamp'])
VCB_data.set_index('Date', inplace=True)
VCB_data.sort_index(inplace=True)

# Define the window size (360 days) and prepare train and test data
window_size = 360
shift_periods = 30  

# Create a list to store predictions and actual values
predictions = []
actuals = []

# Shift the 'Close' column to create the target variable for the next month
VCB_data['Target'] = VCB_data['close'].shift(-shift_periods)

# Drop rows with NaN values in the 'Target' column
VCB_data.dropna(subset=['Target'], inplace=True)

# Iterate over the dataset with a rolling window
for i in range(window_size, len(VCB_data)):
    train_data = VCB_data.iloc[i-window_size:i]
    test_data = VCB_data.iloc[i:i+1]
    
    X_train = train_data[['open', 'high', 'low', 'volume', 'close']]
    y_train = train_data['Target']
    X_test = test_data[['open', 'high', 'low', 'volume', 'close']]
    y_test = test_data['Target']
    
    # Fit the model
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Predict the next month's closing price
    prediction = model.predict(X_test)
    predictions.append(prediction[0])
    actuals.append(y_test.values[0])

# Convert predictions and actuals to numpy arrays for evaluation
predictions = np.array(predictions)
actuals = np.array(actuals)

# Calculate evaluation metrics
rmse = np.sqrt(mean_squared_error(actuals, predictions))

# Evaluation
print("Root Mean Square Error (RMSE):", rmse)

dates = VCB_data.index[window_size:window_size + len(predictions)]

plt.figure(figsize=(14, 7))
plt.plot(dates, actuals, label='Actual', color='b')
plt.plot(dates, predictions, label='Predicted', color='r', linestyle='--')
plt.xlabel('Date')
plt.ylabel('Closing Price')
plt.title('Actual vs Predicted Closing Prices Over Time')
plt.legend()
plt.show()
```

<figure><img src="/files/HVVPe9mLOAva77gOJdRt" alt=""><figcaption><p>Linear Regression model prediction versus actual price.</p></figcaption></figure>

### 2. Random Forest/ XG Boost

{% hint style="info" %}

* **Main idea**: The model uses multiple Decision Trees to make predictions, averaging their outputs to reduce overfitting.
* **Advantages**:
  * Doesn't require data to have linear relationships.
  * Robust with data influenced by many factors.
* **Disadvantages**:
  * Slower than Linear Regression with large datasets.
  * Not ideal for time series forecasting as it lacks the ability to remember past information.
    {% endhint %}

```python
# Convert Date column to datetime
VCB_data['Date'] = pd.to_datetime(VCB_data['timestamp'])
VCB_data.set_index('Date', inplace=True)
VCB_data.sort_index(inplace=True)

# Define the window size (360 days) and prepare train and test data
window_size = 360
shift_periods = 30  

# Create a list to store predictions and actual values
predictions = []
actuals = []

# Shift the 'Close' column to create the target variable for the next month
VCB_data['Target'] = VCB_data['close'].shift(-shift_periods)

# Drop rows with NaN values in the 'Target' column
VCB_data.dropna(subset=['Target'], inplace=True)

# Iterate over the dataset with a rolling window
for i in range(window_size, len(VCB_data)):
    train_data = VCB_data.iloc[i-window_size:i]
    test_data = VCB_data.iloc[i:i+1]
    
    X_train = train_data[['open', 'high', 'low', 'volume', 'close']]
    y_train = train_data['Target']
    X_test = test_data[['open', 'high', 'low', 'volume', 'close']]
    y_test = test_data['Target']
    
    # Fit the model using Random Forest
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    
    # Predict the next month's closing price
    prediction = model.predict(X_test)
    predictions.append(prediction[0])
    actuals.append(y_test.values[0])

# Convert predictions and actuals to numpy arrays for evaluation
predictions = np.array(predictions)
actuals = np.array(actuals)

# Calculate evaluation metrics
rmse = np.sqrt(mean_squared_error(actuals, predictions))

# Evaluation
print("Root Mean Square Error (RMSE):", rmse)

last_30_predictions = predictions[-30:]
last_30_actuals = actuals[-30:]
last_30_dates = VCB_data.index[window_size + len(predictions) - 30:window_size + len(predictions)]

# Plot the last 30 predictions vs the last 30 actuals
plt.figure(figsize=(14, 7))
plt.plot(last_30_dates, last_30_actuals, label='Actual', color='b')
plt.plot(last_30_dates, last_30_predictions, label='Predicted', color='r', linestyle='--')
plt.xlabel('Date')
plt.ylabel('Closing Price')
plt.title('Last 30 Actual vs Predicted Closing Prices')
plt.legend()
plt.show()

```

<figure><img src="/files/fgFUUcSXefhDZb4BlZ7d" alt=""><figcaption><p>Predicted price vs actual price</p></figcaption></figure>

### 3. Long short-term memory network (LSTM)&#x20;

{% hint style="info" %}

* **Main idea**: This is a variant of the Recurrent Neural Network (RNN) that can remember information for long periods thanks to its gating mechanism.
* **Application in stock price prediction**: The model can learn trends and patterns from past price data to predict future prices.
* **Advantages**:
  * Excellent at processing time series data.
  * Can learn long-term trends.
* **Disadvantages**:
  * Requires large datasets to achieve good performance.
  * High computational complexity, needs a GPU for fast training.
    {% endhint %}

**For an LSTM network to effectively learn stock price characteristics, it needs additional features beyond open, high, low, and volume.**

* **Create a "Label" column, which is the 'Close' price of the previous day.**

```python
data['Label'] = data['close'].shift(-1)
```

* **Tạo thêm feature**

<pre class="language-python"><code class="lang-python">def alpha_generate(df):
 # 2. Volume Weighted Average Price (VWAP)
    df['VWAP'] = (df['volume'] * (df['high'] + df['low'] + df['close']) / 3).cumsum() / df['volume'].cumsum()
    df['alpha1'] = (df['high'] * df['low']) ** 0.5 - df['VWAP']
    df['alpha2'] = (df['close'] - df['open']) / ((df['high'] - df['low']) + 0.001)
    df['p3'] = df['close'].shift(3).bfill()
    df['p6'] = df['close'].shift(6).bfill()
    # 3. Relative Strength Index (RSI)
    def calculate_rsi(df, window=9):
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
        loss = (-delta.where(delta &#x3C; 0, 0)).rolling(window=window).mean()
        RS = gain / loss
        df['RSI'] = 100 - (100 / (1 + RS))
        df['RSI'] = df['RSI'].bfill()

    calculate_rsi(df)
    def calculate_ewma(close_prices, alpha):
        return close_prices.ewm(alpha=0.9).mean()

<strong>    def calculate_lagged_return(prices, lag):
</strong>        log_returns = np.log(prices) - np.log(prices).shift(lag)
        return log_returns.bfill()
    
    df['lag_1'] = calculate_lagged_return(df['close'], 1)
    df['lag_2'] = calculate_lagged_return(df['close'], 2)
#TODO: USER NEEDS TO CHOOSE THEIR OWN FEATURE ENGINEERING 
</code></pre>

```python
data = alpha_generate(data)
```

* **Standardize data**

```python
data = data.set_index('date')
close_max = data['close'].max()
close_min = data['close'].min()
data.drop(['stt', 'ticker', 'name'], axis=1, inplace=True)
columns = data.columns
scaler = MinMaxScaler()
data = pd.DataFrame(scaler.fit_transform(data), columns=columns, index=data.index)
data
```

* **Model**&#x20;

```python
class LSTMModel(nn.Module):
    def __init__(self, d_feat=6, hidden_size=64, num_layers=2, dropout=0.0):
        super().__init__()

        self.rnn = nn.LSTM(
            input_size=d_feat,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout,
        )
        self.fc_out = nn.Linear(hidden_size, 1)

        self.d_feat = d_feat

    def forward(self, x):
        # x: [N, F*T]
        x = x.reshape(len(x), self.d_feat, -1)  # [N, F, T]
        x = x.permute(0, 2, 1)  # [N, T, F]
        out, _ = self.rnn(x)
        return self.fc_out(out[:, -1, :]).squeeze()
d_feat = 6
hidden_size = 128
num_layers = 2
dropout = 0.05
n_epochs = 1000
lr = 0.00001
batch_size=7
early_stop=1000
loss="mse"
optimizer="adam"
GPU=0

device = torch.device('mps') if torch.backends.mps.is_available() else 'cpu'
device

lstm_model = LSTMModel(
    d_feat=d_feat,
    hidden_size=hidden_size,
    num_layers=num_layers,
    dropout=dropout,
)
lstm_model = lstm_model.to(device)

def loss_fn(pred, label):
    mask = ~torch.isnan(label)
    loss = (pred[mask] - label[mask]) ** 2
    return torch.mean(loss)

if optimizer.lower() == "adam":
    train_optimizer = optim.Adam(lstm_model.parameters(), lr=lr)
if optimizer.lower() == "gd":
    train_optimizer = optim.SGD(lstm_model.parameters(), lr=lr)
```

.....

<figure><img src="/files/N18tgeAHLFD8vpBN9W3q" alt=""><figcaption></figcaption></figure>
