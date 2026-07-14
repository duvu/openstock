# Ứng dụng Thực tế - Lấy dữ liệu, Phân tích, Chiến lược Giao dịch

## Phần 21: Ứng dụng Thực tế

### 1. Lấy Dữ liệu Toàn bộ VN30

**Hàm sử dụng:**
```python
from FiinQuantX import FiinSession
import pandas as pd

client = FiinSession(username='your_username', password='your_password').login()

# Lấy danh sách VN30
vn30_symbols = client.get_symbols_by_index('VN30')

# Lấy dữ liệu lịch sử cho tất cả mã
all_data = {}

for symbol in vn30_symbols:
    df = client.get_historical_data(
        symbol=symbol,
        from_date='2024-01-01',
        to_date='2024-01-31',
        resolution='1D'
    )
    all_data[symbol] = df

# Kết hợp dữ liệu vào một DataFrame
close_prices = pd.DataFrame({
    symbol: all_data[symbol]['close'] 
    for symbol in vn30_symbols
})

print(close_prices)
```

### 2. Tính Lợi nhuận & Rủi ro

**Hàm sử dụng:**
```python
import numpy as np

# Tính lợi nhuận hàng ngày
daily_returns = close_prices.pct_change()

# Tính lợi nhuận trung bình hàng năm
annual_return = daily_returns.mean() * 252

# Tính độ rủi ro (Standard Deviation)
annual_volatility = daily_returns.std() * np.sqrt(252)

# Tính Sharpe Ratio (rủi ro trên 1 đơn vị lợi nhuận)
risk_free_rate = 0.02  # 2% lãi suất phi rủi ro
sharpe_ratio = (annual_return - risk_free_rate) / annual_volatility

# So sánh
comparison = pd.DataFrame({
    'Annual Return': annual_return,
    'Annual Volatility': annual_volatility,
    'Sharpe Ratio': sharpe_ratio
}).sort_values('Sharpe Ratio', ascending=False)

print(comparison)
```

### 3. Xây dựng Portfolio (Danh mục Đầu tư)

**Phương pháp 1: Equally-Weighted (Trọng số bằng nhau)**

```python
# Tạo portfolio với 5 mã VN30
symbols = ['HPG', 'VNM', 'ACB', 'VCB', 'TCB']

# Trọng số bằng nhau (20% mỗi mã)
weights = np.array([0.2, 0.2, 0.2, 0.2, 0.2])

# Lấy dữ liệu
data = {}
for symbol in symbols:
    data[symbol] = client.get_historical_data(
        symbol=symbol,
        from_date='2023-01-01',
        to_date='2024-01-31',
        resolution='1D'
    )

# Tính lợi nhuận portfolio
returns = pd.DataFrame({
    symbol: data[symbol]['close'].pct_change() 
    for symbol in symbols
})

portfolio_return = (returns * weights).sum(axis=1)

# Tính lợi nhuận tích lũy
cumulative_return = (1 + portfolio_return).cumprod()

print("Portfolio Return:")
print(cumulative_return)
```

**Phương pháp 2: Market-Cap Weighted (Trọng số theo vốn hóa)**

```python
# Lấy vốn hóa
market_caps = {}
for symbol in symbols:
    market_caps[symbol] = client.get_market_cap(symbol)

# Tính trọng số
total_market_cap = sum(market_caps.values())
weights = np.array([market_caps[s] / total_market_cap for s in symbols])

print("Market Cap Weights:")
for symbol, weight in zip(symbols, weights):
    print(f"{symbol}: {weight:.2%}")

# Tính lợi nhuận portfolio
portfolio_return = (returns * weights).sum(axis=1)
cumulative_return = (1 + portfolio_return).cumprod()

print("Market Cap Weighted Portfolio Return:")
print(cumulative_return.tail())
```

### 4. Phân tích Tương quan (Correlation Analysis)

```python
# Tính ma trận tương quan
correlation_matrix = returns.corr()

print("Correlation Matrix:")
print(correlation_matrix)

# Vẽ biểu đồ tương quan
import matplotlib.pyplot as plt
import seaborn as sns

sns.heatmap(correlation_matrix, annot=True, fmt='.2f', cmap='coolwarm')
plt.title('Correlation Matrix - VN30 Stocks')
plt.show()

# Tìm mã có tương quan cao nhất
high_corr = correlation_matrix.unstack().sort_values(ascending=False)
print("Highest Correlations:")
print(high_corr[high_corr < 1].head())
```

### 5. Phân tích Động lực (Momentum Analysis)

```python
# Tính Momentum (thay đổi % so với 20 ngày trước)
momentum_20 = close_prices.pct_change(20)

# Tìm mã có Momentum dương
positive_momentum = momentum_20[momentum_20 > 0].sum()
print("Stocks with positive 20-day momentum:")
print(positive_momentum.sort_values(ascending=False))

# Xác định mã đang uptrend
uptrend_symbols = close_prices[close_prices > close_prices.rolling(50).mean()].dropna(how='any').index[-1]
print("Symbols in uptrend:")
print(uptrend_symbols)
```

### 6. Chiến lược Giao dịch Golden Cross

```python
def golden_cross_strategy(symbol, from_date, to_date):
    """
    Golden Cross: SMA(50) cắt SMA(200) từ dưới lên = Tín hiệu mua
    Death Cross: SMA(50) cắt SMA(200) từ trên xuống = Tín hiệu bán
    """
    
    # Lấy dữ liệu
    df = client.get_historical_data(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        resolution='1D'
    )
    
    # Tính SMA
    df['SMA50'] = df['close'].rolling(window=50).mean()
    df['SMA200'] = df['close'].rolling(window=200).mean()
    
    # Tính tín hiệu
    df['Signal'] = 0
    df.loc[df['SMA50'] > df['SMA200'], 'Signal'] = 1  # Mua
    df.loc[df['SMA50'] < df['SMA200'], 'Signal'] = -1  # Bán
    
    # Tìm điểm giao cắt
    df['Position'] = df['Signal'].diff()
    
    # Buy Signal: Position = 2 (từ -1 sang 1)
    # Sell Signal: Position = -2 (từ 1 sang -1)
    
    buy_signals = df[df['Position'] == 2].copy()
    sell_signals = df[df['Position'] == -2].copy()
    
    return {
        'data': df,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals
    }

# Áp dụng chiến lược
result = golden_cross_strategy('HPG', '2023-01-01', '2024-01-31')

print("Buy Signals:")
print(result['buy_signals'][['close', 'SMA50', 'SMA200']])

print("\nSell Signals:")
print(result['sell_signals'][['close', 'SMA50', 'SMA200']])
```

### 7. Chiến lược RSI + MACD

```python
def rsi_macd_strategy(symbol, from_date, to_date):
    """
    Buy: RSI < 30 và MACD > Signal (đồng thời)
    Sell: RSI > 70 hoặc MACD < Signal
    """
    
    # Lấy dữ liệu + chỉ báo
    df = client.get_historical_data(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        resolution='1D'
    )
    
    # Thêm RSI
    rsi = client.get_technical_indicator(symbol, indicator='RSI', period=14)
    df['RSI'] = rsi['RSI_14']
    
    # Thêm MACD
    macd = client.get_technical_indicator(symbol, indicator='MACD')
    df['MACD'] = macd['MACD']
    df['MACD_Signal'] = macd['MACD_Signal']
    
    # Tín hiệu
    df['Position'] = 0
    
    # Buy: RSI < 30 và MACD > Signal
    buy_condition = (df['RSI'] < 30) & (df['MACD'] > df['MACD_Signal'])
    df.loc[buy_condition, 'Position'] = 1
    
    # Sell: RSI > 70 hoặc MACD < Signal
    sell_condition = (df['RSI'] > 70) | (df['MACD'] < df['MACD_Signal'])
    df.loc[sell_condition, 'Position'] = -1
    
    buy_signals = df[df['Position'] == 1]
    sell_signals = df[df['Position'] == -1]
    
    return {
        'data': df,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals
    }

# Áp dụng
result = rsi_macd_strategy('HPG', '2023-01-01', '2024-01-31')
print("Buy Signals:")
print(result['buy_signals'][['close', 'RSI', 'MACD']])
```

### 8. Tính toán Performance (Hiệu suất)

```python
def calculate_performance(df, buy_signals, sell_signals):
    """
    Tính hiệu suất của chiến lược giao dịch
    """
    
    results = []
    
    for i in range(len(buy_signals)):
        if i >= len(sell_signals):
            break
        
        buy_price = buy_signals.iloc[i]['close']
        buy_date = buy_signals.index[i]
        
        sell_price = sell_signals.iloc[i]['close']
        sell_date = sell_signals.index[i]
        
        profit_loss = sell_price - buy_price
        profit_loss_pct = (profit_loss / buy_price) * 100
        
        holding_days = (sell_date - buy_date).days
        
        results.append({
            'Buy Date': buy_date,
            'Buy Price': buy_price,
            'Sell Date': sell_date,
            'Sell Price': sell_price,
            'Profit/Loss': profit_loss,
            'Profit/Loss %': profit_loss_pct,
            'Holding Days': holding_days
        })
    
    df_results = pd.DataFrame(results)
    
    # Tính tổng
    total_trades = len(df_results)
    winning_trades = len(df_results[df_results['Profit/Loss'] > 0])
    losing_trades = len(df_results[df_results['Profit/Loss'] < 0])
    win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
    
    avg_profit = df_results['Profit/Loss %'].mean()
    max_profit = df_results['Profit/Loss %'].max()
    max_loss = df_results['Profit/Loss %'].min()
    
    print(f"Total Trades: {total_trades}")
    print(f"Winning Trades: {winning_trades} ({win_rate:.1f}%)")
    print(f"Losing Trades: {losing_trades}")
    print(f"Average Profit/Loss: {avg_profit:.2f}%")
    print(f"Max Profit: {max_profit:.2f}%")
    print(f"Max Loss: {max_loss:.2f}%")
    
    return df_results

# Áp dụng
result = golden_cross_strategy('HPG', '2023-01-01', '2024-01-31')
performance = calculate_performance(
    result['data'],
    result['buy_signals'],
    result['sell_signals']
)

print(performance)
```

### 9. Quản lý Rủi ro (Risk Management)

```python
def calculate_position_size(account_size, risk_percentage, entry_price, stop_loss):
    """
    Tính kích thước lệnh dựa trên quản lý rủi ro
    
    account_size: Tài khoản
    risk_percentage: % rủi ro tối đa (thường 1-2%)
    entry_price: Giá vào
    stop_loss: Giá dừng lỗ
    """
    
    risk_amount = account_size * (risk_percentage / 100)
    price_difference = entry_price - stop_loss
    
    if price_difference <= 0:
        return 0
    
    position_size = risk_amount / price_difference
    
    return int(position_size)

# Ví dụ
account = 100_000_000  # 100 triệu VNĐ
entry = 45.5
stop_loss = 44.0
risk = 2  # 2% rủi ro

position = calculate_position_size(account, risk, entry, stop_loss)
print(f"Position Size: {position:,} shares")
print(f"Risk: {(entry - stop_loss) * position:,} VNĐ")
```

### 10. Backtesting Chiến lược

```python
def backtest_strategy(symbol, strategy_func, from_date, to_date):
    """
    Backtesting đơn giản
    """
    
    # Lấy dữ liệu
    df = client.get_historical_data(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        resolution='1D'
    )
    
    # Áp dụng chiến lược
    signals = strategy_func(df)
    
    # Tính lợi nhuận
    returns = []
    in_position = False
    entry_price = 0
    
    for idx, row in df.iterrows():
        if signals.get(idx) == 'BUY' and not in_position:
            in_position = True
            entry_price = row['close']
        
        elif signals.get(idx) == 'SELL' and in_position:
            exit_price = row['close']
            profit_pct = ((exit_price - entry_price) / entry_price) * 100
            returns.append(profit_pct)
            in_position = False
    
    # Tính tổng
    total_return = sum(returns)
    avg_return = sum(returns) / len(returns) if returns else 0
    num_trades = len(returns)
    
    print(f"Backtesting Results for {symbol}")
    print(f"Total Trades: {num_trades}")
    print(f"Total Return: {total_return:.2f}%")
    print(f"Average Return per Trade: {avg_return:.2f}%")
    print(f"Win Rate: {(len([r for r in returns if r > 0]) / len(returns) * 100):.1f}%")
    
    return returns
```

## Tài liệu liên quan

- [2. Dữ liệu giao dịch](/ham-va-cong-thuc/2.-du-lieu-giao-dich.md)
- [3. Phân tích cơ bản & Định giá](/ham-va-cong-thuc/3.-phan-tich-co-ban-and-dinh-gia.md)
- [8. Danh sách chỉ báo TA](/ham-va-cong-thuc/8.-danh-sach-chi-so-ta.md)
- [10. Bộ lọc cổ phiếu](/ham-va-cong-thuc/10.-bo-loc-co-phieu.md)
