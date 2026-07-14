# Phân tích phái sinh

Ứng dụng tính số điểm tăng/giảm ở các nến và thống kê khi nến 15 phút tăng trên 10 điểm:

```python
import pandas as pd

from FiinQuantX import FiinSession

# Đăng nhập
username = 'REPLACE_WITH_YOUR_USER_NAME'
password = 'REPLACE_WITH_YOUR_PASS_WORD'

client = FiinSession(username=username, password=password).login()

# Lấy dữ liệu nến 15 phút của VN30F1M
event = client.Fetch_Trading_Data(
    realtime=False,
    tickers=["VN30F1M"],
    fields=["open", "close", "volume"],
    adjusted=True,
    by="15m",
    period=1000
)
 
df = event.get_data()
 
# Tính chênh lệch giá và volume trung bình 5 nến
df["diff"] = df["close"] - df["open"]
df["vol_avg_5"] = df["volume"].rolling(window=5).mean()
 
# Lọc nến tăng > 10 điểm
signal_bars = df[df["diff"] > 10].copy()
 
# Tính tỷ lệ volume so với trung bình
signal_bars["vol_ratio"] = signal_bars["volume"] / signal_bars["vol_avg_5"]
 
# Tính số điểm tăng/giảm ở các nến kế tiếp
results = []
for idx in signal_bars.index:
    try:
        base_price = df.loc[idx]["close"]
        point_changes = [
            df.loc[idx+1]["close"] - base_price,
            df.loc[idx+2]["close"] - base_price,
            df.loc[idx+3]["close"] - base_price,
        ]
    except:
        point_changes = [None, None, None]
    results.append(point_changes)
 
signal_bars[["n+1_pts", "n+2_pts", "n+3_pts"]] = pd.DataFrame(results, index=signal_bars.index)
 
# In kết quả chi tiết
print(signal_bars[["timestamp", "open", "close", "diff", "volume", "vol_ratio", "n+1_pts", "n+2_pts", "n+3_pts"]])
 
# Thống kê
print("\n📊 Thống kê khi nến 15' tăng > 10 điểm:")
print(f"Tổng số nến tín hiệu: {len(signal_bars)}")
print(f" - N+1 trung bình: {signal_bars['n+1_pts'].mean():.2f} điểm")
print(f" - N+2 trung bình: {signal_bars['n+2_pts'].mean():.2f} điểm")
print(f" - N+3 trung bình: {signal_bars['n+3_pts'].mean():.2f} điểm")
print(f" - Tỷ lệ volume TB (vol_ratio): {signal_bars['vol_ratio'].mean():.2f} lần")
```

Kết quả trả ra

<figure><img src="/files/CaC289pu3T1Iy8t66Mfc" alt=""><figcaption></figcaption></figure>
