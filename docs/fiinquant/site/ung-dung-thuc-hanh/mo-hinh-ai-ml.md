# Mô hình AI/ML

## Mô hình AI để phân tích giá cổ phiếu trong lịch sử&#x20;

{% hint style="info" %}
Sử dụng các mô hình LLM với data của FiinQuant để hỗ trợ trong việc tìm ra các insight theo yêu cầu của người dùng
{% endhint %}

```python
import requests
import google.generativeai as genai
import pandas as pd

from FiinQuantX import FiinSession
from bs4 import BeautifulSoup

GOOGLE_GEMINI_API_KEY = 'YOUR_GOOGLE_GEMINI_API_KEY'
genai.configure(api_key=GOOGLE_GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")


```

```python
username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(
    username=username,
    password=password
).login()

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

## Mô Hình Machine Learning dự đoán giá cổ phiếu&#x20;

Lấy dữ liệu cổ phiếu từ thư viện Fiinquant

<pre class="language-python"><code class="lang-python">import pandas as pd
import numpy as np

from FiinQuantX import FiinSession
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
from sklearn.ensemble import RandomForestRegressor

username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

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
**Linear Regression (Hồi quy tuyến tính)**

* **Ý tưởng chính**: Mô hình dự đoán giá cổ phiếu bằng cách tìm một đường thẳng phù hợp nhất với dữ liệu quá khứ. Công thức tổng quát: y=w0+w1x1+w2x2+...+wnxn+ϵy = w\_0 + w\_1 x\_1 + w\_2 x\_2 + ... + w\_n x\_n + \epsilony=w0​+w1​x1​+w2​x2​+...+wn​xn​+ϵ với yyy là giá cổ phiếu, xix\_ixi​ là các yếu tố ảnh hưởng như giá mở cửa, khối lượng giao dịch,...
* **Ưu điểm**: Đơn giản, dễ hiểu, tính toán nhanh.
* **Nhược điểm**: Giả định mối quan hệ tuyến tính giữa các biến, khó bắt được sự phi tuyến của giá cổ phiếu.
  {% endhint %}

Chuẩn bị dữ liệu và chạy mô hình

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

<figure><img src="/files/HVVPe9mLOAva77gOJdRt" alt=""><figcaption><p>Mô hình Linear Regression dự đoán so với giá thực tế</p></figcaption></figure>

### 2. Random Forest/ XG Boost

{% hint style="info" %}

* **Ý tưởng chính**: Mô hình sử dụng nhiều cây quyết định (**Decision Trees**) để đưa ra dự đoán trung bình từ các cây đó, giúp giảm overfitting.
* **Ưu điểm**:
  * Không yêu cầu dữ liệu phải có quan hệ tuyến tính.
  * Mạnh mẽ với dữ liệu có nhiều yếu tố tác động.
* **Nhược điểm**:
  * Chậm hơn so với Linear Regression khi dữ liệu lớn.
  * Không tốt trong việc dự đoán chuỗi thời gian do không có khả năng ghi nhớ thông tin quá khứ.
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

<figure><img src="/files/fgFUUcSXefhDZb4BlZ7d" alt=""><figcaption><p>Giá dự đoán so với giá thực tế</p></figcaption></figure>

### 3. Long short-term memory network (LSTM)&#x20;

{% hint style="info" %}

* **Ý tưởng chính**: Là một biến thể của mạng **Recurrent Neural Network (RNN)**, giúp ghi nhớ thông tin trong thời gian dài nhờ cơ chế cổng kiểm soát.
* **Ứng dụng trong dự đoán giá cổ phiếu**: Mô hình có thể học được xu hướng và các mẫu từ dữ liệu giá quá khứ để dự đoán giá tương lai.
* **Ưu điểm**:
  * Tốt trong việc xử lý chuỗi thời gian.
  * Có thể học được xu hướng dài hạn.
* **Nhược điểm**:
  * Yêu cầu dữ liệu lớn để đạt hiệu quả tốt.
  * Độ phức tạp tính toán cao, cần GPU để huấn luyện nhanh.

{% endhint %}

**Mạng LSTM cần thêm features ngoài Open High Low Volume để học được tính chất giá của cổ phiếu**

* **Tạo cột Label chính là giá 'Close' của ngày hôm trước**&#x20;

```python
data['Label'] = data['close'].shift(-1)
```

* Tạo th**êm feature**

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

* Chuẩn hoá dữ liệu&#x20;

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
