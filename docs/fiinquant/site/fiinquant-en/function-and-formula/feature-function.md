# Feature function

### Rebalance function

By inputting the investable value and the index code, the algorithm will calculate the quantity of shares needed to most closely match the proportion of stocks in the index basket. This is applied in arbitrage trading and passive investment.

{% hint style="info" %}
The Rebalance function utilizes publicly available data from the Stock Exchange regarding **Free-float Ratio** and **Marketcap Limit**, combined with real-time **closing prices** from the FiinGroup system.

Rebalancing is performed based on the principle that the **proportion of volume remains unchanged within a portfolio**. Therefore, to effectively track an index, a portfolio manager only needs to construct a portfolio where the proportional quantity of shares matches the proportion of the index being tracked. This approach ensures the lowest possible **Tracking Error**.

The output is "Share to Buy", based on the input of the **Budget (VND)** and the **Ticker (Index)** to be rebalanced.
{% endhint %}

<figure><img src="/files/a4wvKfK4eKf1szx4y7j3" alt="" width="375"><figcaption><p>Danh sách vã số lượng cần mua của mỗi mã cổ phiếu</p></figcaption></figure>

```python
import FiinQuantX as fq
                     
client = fq.FiinSession(username=username, password=password).login()
df = client.Rebalance().get(Budget = 10000000000, Ticker = 'VN30')
print(df)
```

<figure><img src="/files/C5HGpXBNPdoUhLoRpFv7" alt=""><figcaption></figcaption></figure>

## SimilarChart function

{% hint style="info" %}
Allows users to quickly search through a large number of stock codes to find the 5 codes with the closest price trends to the stock of interest.
{% endhint %}

<figure><img src="/files/uEPJD4gIaet3gF3FR5Ua" alt=""><figcaption><p>5 mã cổ phiếu có xu hướng gần nhất với mã ACB hiện tại </p></figcaption></figure>

```python
client.SimilarChart().plot(Ticker=Ticker, t1=t1, t2=t2)
```

**Parameter**

| Paraneter | Description                      | Data type | Default |
| --------- | -------------------------------- | --------- | ------- |
| Ticker    | Applied ticker code              | Ticker    | None    |
| t1        | Start time of the candle cluster | str       |         |
| t2        | End time of the candle cluster   | str       |         |

```python
import pandas as pd
from FiinQuantX import FiinSession
import datetime
from datetime import datetime
from dateutil.relativedelta import relativedelta


username = 'YOUR_USERNAME'  # Input your username here 
password = 'YOUR_PASSWORD'    # Input your password here 
client = FiinSession(
    username=username,
    password=password
).login()

def user_input():
    default_t1 = (datetime.now() - relativedelta(months=1)).strftime("%Y-%m-%d")
    default_t2 = datetime.now().strftime("%Y-%m-%d")
    print("")
    print("Chào mừng đến hệ thống dự báo biểu đồ CHỨNG KHOÁN theo THỜI GIAN THỰC của FIINQUANT")
    print("")
    print("Giải thích cách tìm chart có đường giá tương đồng với đường giá thời điểm hiện tại:")
    print("")
    print("- Tìm kiếm tất cả các pattern nến của tất cả các ngày trong vòng x năm kể từ thời điểm hiện tại")
    print("- Tìm ngày có đường giá giống với ngày hiện tại nhất")
    print("")
    print("Hệ thống sẽ sử dụng các tham số mặc định sau:")
    print(f'- Thời điểm bắt đầu: {default_t1}')
    print(f'- Thời điểm kết thúc (là thời điểm hiện tại): {default_t2}')

    use_default = input("Bạn có muốn sử dụng các tham số mặc định không? (y/n): ").lower() == "y"

    if not use_default:
        t1 = input("Nhập ngày bắt đầu (ví dụ: 2024-05-10): ")
        t2 = input("Nhập thời điểm kết thúc (ví dụ: 2024-05-10): ")
    else:
        t1 = default_t1
        t2 = default_t2
    
    Ticker = input("Vui lòng nhập mã bạn muốn so tìm đường tương quan (ví dụ: VN30, VN30F1M, ACB): ")
    Ticker = Ticker.upper()    
    print("Đang tính toán, vui lòng đợi")
    client.SimilarChart().plot(Ticker=Ticker, t1=t1, t2=t2)

if __name__ == "__main__":
    user_input()
```

<figure><img src="/files/jzd00wya8KTwV3Xi7Auu" alt=""><figcaption></figcaption></figure>

## FindDateCorrelation function

{% hint style="info" %}
Use this function to find the correlation between today's data and historical data for a specific code.
{% endhint %}

<figure><img src="/files/dxAhFH3lP5Aa7DDBU0PQ" alt=""><figcaption><p>Ví dụ tìm kiếm tương quan cho VN30F1M trong 1 năm dữ liệu so với ngày hiện tại</p></figcaption></figure>

<pre class="language-python"><code class="lang-python">
 def intraday_Correlation(self, Ticker: Union[str, list[str]], Timeframe: str, 
                            t1: str = None, t2: str = None, method: str = "pearson correlation",
<strong>                            year: int = 1) -> None:
</strong></code></pre>

#### Parameter

<table><thead><tr><th>Parameter</th><th>Data type</th><th>Default</th><th>Default value</th><th width="202.828125">Description</th></tr></thead><tbody><tr><td><code>Ticker</code></td><td><code>Union[str, list[str]]</code></td><td>Required</td><td>None</td><td>Stock code or list of stock codes to analyze</td></tr><tr><td><code>Timeframe</code></td><td><code>str</code></td><td>Required</td><td>1M </td><td>Intraday trading data timeframe (e.g., '1m', '5m', '1h').</td></tr><tr><td><code>t1</code></td><td><code>str</code></td><td>Optional</td><td>9am or 13pm </td><td>Start time (if needed).</td></tr><tr><td><code>t2</code></td><td><code>str</code></td><td>Optional</td><td><code>None</code></td><td>End time (if needed).</td></tr><tr><td><code>method</code></td><td><code>str</code></td><td>Optional</td><td><code>"pearson correlation"</code></td><td>Distance measurement method (1: Euclidean, 2: DTW, 3: Pearson, 4: Cosine).</td></tr><tr><td><code>year</code></td><td><code>int</code></td><td>Optional</td><td><code>1</code></td><td>Number of past years of data to compare.</td></tr></tbody></table>

Copy the code snippet to run the example above.

```python

import pandas as pd
from FiinQuantX import FiinSession
import datetime
from datetime import datetime
username = 'YOUR_USERNAME'  # Input your username here 
password = 'YOUR_PASSWORD'    # Input your password here 
client = FiinSession(
    username=username,
    password=password
).login()

def user_input():
    default_timeframe = '1m'
    default_t1 = "09:00:00" if datetime.now().hour < 12 else "13:00:00"
    default_t2 = datetime.now().replace(microsecond=0).time().strftime("%H:%M:%S")
    default_method = "pearson correlation"
    default_year = 1
    print("")
    print("Chào mừng đến hệ thống dự báo biểu đồ CHỨNG KHOÁN theo THỜI GIAN THỰC của FIINQUANT")
    print("")
    print("Giải thích cách tìm top 5 ngày tương quan:")
    print("")
    print("- Tìm kiếm tất cả các pattern nến của tất cả các ngày trong vòng x năm kể từ thời điểm hiện tại")
    print("- Tìm 5 ngày có độ tương quan với ngày hiện tại nhất dựa trên các phương pháp tùy người chọn: Euclidean Distance, Pearson Correlation (mặc định), cosine")
    print("")
    print("Hệ thống sẽ sử dụng các tham số mặc định sau:")
    print(f"- Khung thời gian: {default_timeframe}")
    print(f"- Thời điểm bắt đầu: {default_t1}")
    print(f"- Thời điểm kết thúc (là thời điểm hiện tại): {default_t2}")
    print(f"- Phương pháp tính tương quan: {default_method}")
    print(f"- Số năm dữ liệu muốn quét kể từ thời điểm hiện tại: {default_year} năm")

    use_default = input("Bạn có muốn sử dụng các tham số mặc định không? (y/n): ").lower() == "y"

    if not use_default:
        timeframe = input("Nhập khung thời gian (ví dụ: 1m, 15m, 30m, 1h mặc định: 1m): ") or default_timeframe
        t1 = input("Nhập thời điểm bắt đầu (ví dụ: 09:00, 10:00, 11:00): ")
        t2 = input("Nhập thời điểm kết thúc (ví dụ: 13:00, 14:00, 15:00): ")
        
        print("Vui lòng lựa chọn phương pháp tính tương quan:")
        print("1. Pearson Correlation (mặc định)")
        print("2. Euclidean Distance")
        print("3. Cosine")
        print("4. Dynamic Time Wrapping")
        method = int(input("Lựa chọn của bạn (1/2/3): ")) or 1
        
        year = int(input("Nhập số năm dữ liệu muốn quét kể từ thời điểm hiện tại: ")) or 1
    else:
        timeframe = default_timeframe
        t1 = default_t1
        t2 = default_t2
        method = default_method
        year = default_year
    
    Ticker = input("Vui lòng nhập mã bạn muốn so tìm đường tương quan (ví dụ: VN30, VN30F1M, ACB): ")
    print("Đang tính toán, vui lòng đợi")
    client.FindDateCorrelation().intraday_Correlation(Ticker=Ticker, Timeframe=timeframe, t1=t1, t2=t2, method=method, year=year)


# Chạy chương trình
if __name__ == "__main__":
    user_input()

```

<figure><img src="/files/txsuotdzA1dGVpVAlLi6" alt=""><figcaption><p>Output khi chạy đoạn code trên </p></figcaption></figure>

## SeasonalityPrice function

{% hint style="info" %}
This function is used to plot the correlation of price changes for one or more stock codes over a period.
{% endhint %}

```python
import pandas as pd
import numpy as np
from plotly import graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import FiinQuantX as fq

client = fq.FiinSession('USERNAME', 'PASSWORD').login()

class SeasonalityPrice:
    def __init__(self, data, tickers):
        self.data = data
        self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
        self.tickers = []
        if isinstance(tickers, str):
            self.tickers = [tickers]
        elif isinstance(tickers, list):
            self.tickers = tickers
        else:
            self.tickers = [tickers]

    def monthly_seasonality(self):
        if len(self.tickers) > 1:
            raise ValueError("Only one ticker is supported for monthly seasonality")
        
        filtered_data = self.data.copy()
        filtered_data.set_index('timestamp', inplace=True)

        monthly_returns = filtered_data['close'].resample('M').last().pct_change() * 100
        monthly_seasonality = pd.DataFrame()
        monthly_seasonality['Month'] = monthly_returns.index.month
        monthly_seasonality['Year'] = monthly_returns.index.year
        monthly_seasonality['Returns'] = monthly_returns.values

        return monthly_seasonality
    
    
    def plot_seasonality(self):  
        if len(self.tickers) > 1:
            print("Tickers: ", self.tickers)

            raise ValueError("Only one ticker is supported for monthly seasonality")
        
        monthly_seasonality = self.monthly_seasonality()
        pivot_table = monthly_seasonality.pivot(index='Year', columns='Month', values='Returns').sort_index(ascending=True)
        monthly_averages = pivot_table.mean(axis=0).values.reshape(1, -1)  
        monthly_stdev = pivot_table.std(axis=0).values.reshape(1, -1)
        monthly_avg_plus_stdev = monthly_averages + monthly_stdev
        monthly_avg_minus_stdev = monthly_averages - monthly_stdev
        monthly_Sharpe_ratio = monthly_averages / monthly_stdev
        annotations = []
        for i, row in enumerate(pivot_table.values):
            for j, value in enumerate(row):
                annotations.append(
                    dict(
                        x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'][j],
                        y=pivot_table.index[i],
                        text=f'{value:.2f}' if not np.isnan(value) else '',
                        showarrow=False,
                        font=dict(color='black' if abs(value) < 10 else 'white')
                    )
                )
        fig = go.Figure()

        fig.add_trace(go.Heatmap(
            z=pivot_table.values,
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=pivot_table.index,  
            colorscale=[
                [0, 'darkred'],      
                [0.49, '#ff6666'],   
                [0.5, 'white'],      
                [0.51, '#99ff99'],   
                [1, 'darkgreen']     
            ],
            colorbar_title="Returns (%)",
            showscale=False,
            zmin=-20,   
            zmax=20,
        ))

        # Add the averages heatmap
        fig.add_trace(go.Heatmap(
            z=monthly_averages,
            x= ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=['Avgs: '],
            colorscale=[
                [0, 'darkred'],      
                [0.49, '#ff6666'],   
                [0.5, 'white'],      
                [0.51, '#99ff99'],   
                [1, 'darkgreen']     
            ],
            showscale=False,
            showlegend=False,
            text=monthly_averages,
            texttemplate='%{z:.2f}%',
            yaxis='y2',  
            xaxis='x2', 
        ))

        fig.add_trace(go.Heatmap(
            z=monthly_stdev,
            x= ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=['Stdev: '],
            colorscale=[
                [0, 'darkred'],      
                [0.49, '#ff6666'],   
                [0.5, 'white'],      
                [0.51, '#99ff99'],   
                [1, 'darkgreen']     
            ],
            text=monthly_stdev,
            texttemplate='%{z:.2f}%',
            showscale=False,
            showlegend=False,
            yaxis= 'y3',
            xaxis= 'x3',
        ))
        fig.add_trace(go.Heatmap(
            z=monthly_avg_plus_stdev,
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=['+ 1 stdev: '],
            colorscale=[
                [0, 'darkred'],      
                [0.49, '#ff6666'],   
                [0.5, 'white'],      
                [0.51, '#99ff99'],   
                [1, 'darkgreen']     
            ],
            showscale=False,
            showlegend=False,
            text=monthly_avg_plus_stdev,
            texttemplate='%{z:.2f}%',
            yaxis='y4',
            xaxis='x4',
        ))

        # Add the avg - 1stdev heatmap
        fig.add_trace(go.Heatmap(
            z=monthly_avg_minus_stdev,
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=[' -1 stdev: '],
            colorscale=[
                [0, 'darkred'],      
                [0.49, '#ff6666'],   
                [0.5, 'white'],      
                [0.51, '#99ff99'],   
                [1, 'darkgreen']     
            ],
            showscale=False,
            showlegend=False,
            text=monthly_avg_minus_stdev,
            texttemplate='%{z:.2f}%',
            yaxis='y5',
            xaxis='x5',
        ))

        fig.update_layout(
            title=f'Monthly Percentage Price Change for {self.tickers} (2018-2024)',
            xaxis=dict(domain=[0, 1], showticklabels=False),
            yaxis=dict(domain=[0.5, 1.0], title='Year', autorange='reversed'),  
            xaxis2=dict(domain=[0, 1], anchor='y2', matches='x', showticklabels=False),
            yaxis2=dict(domain=[0.35,0.45], autorange='reversed'), 
            xaxis3=dict(domain=[0, 1], anchor='y3', matches='x',showticklabels=False),
            yaxis3=dict(domain=[0.24,0.34], autorange='reversed'), 
            yaxis4=dict(domain=[0.13,0.23], autorange='reversed'), 
            xaxis4=dict(domain=[0, 1], anchor='y4', matches='x', showticklabels=False),
            yaxis5=dict(domain=[0.02,0.12], autorange='reversed'), 
            xaxis5=dict(domain=[0, 1], anchor='y5', matches='x', title='Month'),
            annotations=annotations,
        )

        fig.show()

        fig_sharpe = go.Figure()

        sharpe_values = monthly_Sharpe_ratio.flatten()
        colors = ['#ff9999' if x < 0 else '#66b3ff' if x < 1 else '#99ff99' for x in sharpe_values]

        fig_sharpe.add_trace(go.Bar(
            x=['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'],
            y=sharpe_values,
            marker_color=colors,
            name='Sharpe Ratio'
        ))

        fig_sharpe.update_layout(
            title=f'Monthly Sharpe Ratio for {self.tickers} (2018-2024)',
            xaxis=dict(title='Month'),
            yaxis=dict(title='Sharpe Ratio'),
            plot_bgcolor='white',
            paper_bgcolor='white',
            showlegend=False,
            bargap=0.2
        )

        fig_sharpe.show()


    def plot_average_sharpe(self):
        monthly_sharpe_ratios = {}
        average_sharpe_ratios = {}

        for ticker in self.tickers:
            # Filter data for the current ticker
            ticker_data = self.data[self.data['ticker'] == ticker]
            ticker_data['timestamp'] = pd.to_datetime(ticker_data['timestamp'])
            mask = (ticker_data['timestamp'] >= '2018-01-01') & (ticker_data['timestamp'] <= '2024-11-30')
            filtered_data = ticker_data[mask].copy()

            filtered_data.set_index('timestamp', inplace=True)
            monthly_returns = filtered_data['close'].resample('ME').last().pct_change() * 100

            # Calculate monthly averages and standard deviations
            monthly_averages = monthly_returns.groupby(monthly_returns.index.month).mean()
            monthly_stdev = monthly_returns.groupby(monthly_returns.index.month).std()

            # Calculate Sharpe ratio
            sharpe_ratios = (monthly_averages / monthly_stdev).values
            monthly_sharpe_ratios[ticker] = sharpe_ratios
            average_sharpe_ratios[ticker] = np.nanmean(sharpe_ratios) 

        # Find the ticker with the highest average Sharpe ratio
        highest_avg_sharpe_ticker = max(average_sharpe_ratios, key=average_sharpe_ratios.get)
        highest_avg_sharpe_value = average_sharpe_ratios[highest_avg_sharpe_ticker]

        # Create subplots
        fig = make_subplots(rows=1, cols=2, shared_yaxes=False, horizontal_spacing=0.1,
                            subplot_titles=("Monthly Sharpe Ratios", "Average Sharpe Ratios"))

        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Plot monthly Sharpe ratios
        for ticker, sharpe_values in monthly_sharpe_ratios.items():
            colors = ['#00FF00' if ticker == highest_avg_sharpe_ticker else '#ff9999' if value < 0 else '#66b3ff' if value < 1 else '#99ff99' for value in sharpe_values]
                    
            fig.add_trace(go.Bar(
                x=months,
                y=sharpe_values,
                marker_color=colors,
                name=f'Sharpe Ratio for {ticker}',
                width=0.15
            ), row=1, col=1)

        # Plot average Sharpe ratios
        avg_sharpe_values = list(average_sharpe_ratios.values())
        avg_colors = ['#00FF00' if ticker == highest_avg_sharpe_ticker else '#66b3ff' for ticker in tickers]
        
        fig.add_trace(go.Bar(
            x=tickers,
            y=avg_sharpe_values,
            marker_color=avg_colors,
            name='Average Sharpe Ratio',
            width=0.4
        ), row=1, col=2)

        # Add annotation for the highest average Sharpe ratio
        fig.add_annotation(
            x=highest_avg_sharpe_ticker, y=highest_avg_sharpe_value,
            text=f"Highest Avg Sharpe: {highest_avg_sharpe_ticker} ({highest_avg_sharpe_value:.2f})",
            showarrow=True,
            arrowhead=1,
            yshift=10,
            font=dict(size=12, color="black"),
            xref="x2", yref="y2"
        )

        fig.update_layout(
            title='Sharpe Ratios for Multiple Tickers (2018-2024)',
            xaxis=dict(title='Month'),
            yaxis=dict(title='Sharpe Ratio'),
            xaxis2=dict(title='Ticker'),
            yaxis2=dict(title='Average Sharpe Ratio', range=[0, max(avg_sharpe_values) * 1.2]),  # Scale y-axis
            plot_bgcolor='white',
            paper_bgcolor='white',
            showlegend=False,
            bargap=0.2
        )

        fig.show()


tickers = ['VCB', 'TPB', 'MBB','VIB','TCB', 'VPB', 'ACB', 'BID','CTG','EIB']

data = client.Fetch_Trading_Data(
    tickers=tickers,
    fields=['close'],
    adjusted=True,
    realtime=False,
    by='1d', 
    from_date='2018-01-01').get_data()
new_SeasonalityPrice = SeasonalityPrice(data, 'VCB')
new_SeasonalityPrice.plot_seasonality()

#Uncomment this to plot average sharpe ratio for multiple tickers
tickers = ['VCB', 'TPB', 'MBB','VIB','TCB', 'VPB', 'ACB', 'BID','CTG','EIB']
# new_SeasonalityPrice = SeasonalityPrice(data, tickers)
# new_SeasonalityPrice.plot_average_sharpe()
```

<figure><img src="/files/8vpI6SolqkPb2c7E1cnD" alt=""><figcaption><p>Monthly price change table for VCB</p></figcaption></figure>

<figure><img src="/files/Rqyr09jvH1FnYRyIIRN1" alt=""><figcaption><p>Sharpe Ratio by month </p></figcaption></figure>
