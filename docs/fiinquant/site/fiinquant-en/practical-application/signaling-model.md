# Signaling model

### 1. Build an alert signal bot

**Purpose:** To build a bot on the Telegram platform that helps alert users about fluctuations in proactive buy/sell activity and foreign investor trading.<br>

**Result when running the bot:**

![](/files/N5h1W47wkC5u6utH8kFZ)&#x20;

**Preparation steps:**

* Create a bot on Telegram, using BotFather on the Telegram application.
* <https://telegram.me/BotFather>

<figure><img src="/files/SItT7vM6gdXGcqOEQDlt" alt=""><figcaption></figcaption></figure>

* After creating the bot, save the API Token.

<figure><img src="/files/BkVl4jGV5ssAAj6PQpLd" alt=""><figcaption></figcaption></figure>

* Create a Telegram group chat and invite the newly created chatbot as a member.
* Turn on the **Topics** feature in the settings of the newly created group.

<figure><img src="/files/cUeSU0esd09rVEQYflKX" alt="" width="250"><figcaption></figcaption></figure>

After creation, users will see "Create a topic." They need to create relevant topics (thread IDs); each topic will have its own unique thread ID.

<figure><img src="/files/MWS16NMsnnVLXXZOGVbL" alt="" width="259"><figcaption></figcaption></figure>

Access <https://web.telegram.org/>, log in with the user's Telegram account.

<figure><img src="/files/eACsNYa98UEDteSGrH10" alt=""><figcaption></figcaption></figure>

After these three steps, users will have the following information:

* Bot's API Token
* Topic ID
* Thread ID

Combine this with your username and password, then fill them into the code sample below to activate the bot.

````python
import time
import requests
from FiinQuantX import FiinSession
from FiinQuantX.Aggregates import BarDataUpdate
from datetime import datetime
from typing import Union, List
 
# ===== 1. KẾT NỐI API FIINQUANT =====
client = FiinSession(
    username='USERNAME',
    password='PASSWORD'
).login()

# ===== 2. CLASS GỬI TELEGRAM =====
class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str, thread_id: str = None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.thread_id = thread_id
 
    def send_message(self, text: str):
        """Gửi tin nhắn Telegram."""
       
        if not self.bot_token or not self.chat_id:
            print("⚠ Lỗi: Chưa cấu hình Telegram!")
            return
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"📤 Bắt đầu gửi tin nhắn lúc: {start_time}")
        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if self.thread_id:
            payload["message_thread_id"] = self.thread_id  # Nếu có THREAD_ID, thêm vào
 
        try:
            response = requests.post(url, data=payload, timeout=5)
            response.raise_for_status()
            print("📩 Đã gửi tin nhắn Telegram thành công!")
        except requests.exceptions.RequestException as e:
            print(f"❌ Lỗi gửi Telegram: {response.status_code} - {response.json()}"
)
 
# ===== 3. CLASS CẢNH BÁO NĐTNN =====
class ForeignWarning:
    def __init__(self, tickers: List[str], timeframe: str, N: int, X: int):
        self.tickers = tickers
        self.timeframe = timeframe
        self.Config = {"N": N, "X": X}
        self.foreign_telegram_notifier = TelegramNotifier('API_TELEGRAM_TOKEN', 'GROUPID', 'THREADID')
        self.busd_telegram_notifier = TelegramNotifier('API_TELEGRAM_TOKEN', 'GROUDID', 'THREADID')
        self.last_timestamp = None  # Lưu timestamp gần nhất
        self.foreign_warned_ticker_times = {}  # Tránh cảnh báo trùng GDNN
        self.busd_warned_ticker_times = {} # Tránh cảnh báo trùng BUSD
        self.data_yesterday = client.Fetch_Trading_Data(
            realtime=False,
            tickers=tickers,    
            fields=['close'],
            adjusted=True,
            by='1d',
            period=1
        ).get_data()
        print(self.data_yesterday)
    def _fetch_realtime_data(self, callback):
        """Lấy dữ liệu giao dịch real-time."""
        event = client.Fetch_Trading_Data(
            realtime=True,
            tickers=self.tickers,
            fields=["close","fn","bu","sd"],
            adjusted=True,
            period=self.Config["X"] + 2,
            by=self.timeframe,
            callback=callback,
            wait_for_full_timeFrame=False
        )
        event.get_data()
        try:
            while not event._stop:
                time.sleep(1)
        except KeyboardInterrupt:
            print("⛔ Dừng theo dõi dữ liệu...")
            event.stop()
 
    def _process_data(self, data: BarDataUpdate):
        """Xử lý dữ liệu và xác định cảnh báo."""
        df = data.to_dataFrame()
 
        # Bỏ cây nến lúc 14:45 nếu timeframe là 1M và 5M
        if self.timeframe in ["1m", "5m"]:
            df = df[~df["timestamp"].str.contains("14:45")]
 
        ticker = df.iloc[-2]["ticker"]
        timestamp = df.iloc[-2]["timestamp"]
        close_price = df.iloc[-2]["close"]  # Giá đóng cửa của nến trước 
        # Tính các chỉ số GDNN
        FNet = df.iloc[-2]["fn"]
        FNetPrev = df.iloc[-3]["fn"]
 
        #Tính các chỉ số BUSD
        BUSD = df.iloc[-2]["bu"] - df.iloc[-2]["sd"]
        BUSDratio = df.iloc[-2]["bu"] / df.iloc[-2]["sd"] if df.iloc[-2]["sd"] != 0 else float("inf")
        BUSDPrev = df.iloc[-3]["bu"] - df.iloc[-3]["sd"]
 
        # Lấy dữ liệu trung bình X timeframe gần nhất
        df_x = df.iloc[0:-2]
 
        # Tính GDNN mua và bán lơn nhất trong lịch sử
        FNetMax = df_x["fn"].max() if not df_x.empty else 0
        FNetMin = df_x["fn"].min() if not df_x.empty else 0
 
        # Tính GDNN mua và bán lơn nhất trong lịch sử
        BUSDMax = (df_x["bu"] - df_x["sd"]).max() if not df_x.empty else 0
        BUSDMin = (df_x["bu"] - df_x["sd"]).min() if not df_x.empty else 0

        # Lấy giá đóng cửa ngày hôm qua từ data_yesterday
        close_yesterday = self.data_yesterday.loc[self.data_yesterday['ticker'] == ticker, 'close'].values

        # Kiểm tra xem có dữ liệu hôm qua không
        if len(close_yesterday) > 0:
            close_yesterday = close_yesterday[0]  # Lấy giá trị đầu tiên
            price_return = ((close_price - close_yesterday) / close_yesterday) * 100
        else:
            price_return = None  # Không có dữ liệu hôm qua thì không tính được

 
        # Nếu mua mạnh
        if FNet > 500000000:
            if FNet > self.Config["N"] * FNetPrev and FNet > 1.3*FNetMax and timestamp != self.foreign_warned_ticker_times.get(ticker):
                if price_return is not None:
                    price_change_text = f"(tăng {price_return:.2f}%)" if price_return > 0 else f"(giảm {abs(price_return):.2f}%)"
                else:
                    price_change_text = ""  # Không có dữ liệu hôm qua thì không hiển thị gì
                msg = (f"📈 <b>CẢNH BÁO: {ticker}</b>\n"
                    f"- NĐTNN <b>mua vào mạnh</b>: {FNet / 1_000_000:.2f} triệu VND trong 1'\n"
                    f"- <b>Giá đóng cửa:</b> {close_price:.0f} {price_change_text}\n"
                    f"- <b>Thời gian</b>: {timestamp}")
                self.foreign_warned_ticker_times[ticker] = timestamp  # Lưu ticker đã cảnh báo
                print(msg)
 
                self.foreign_telegram_notifier.send_message(msg)
 
        # Nếu bán mạnh
        elif FNet < -2000000000:
            if FNet < self.Config["N"] * FNetPrev and FNet < 1.3*FNetMin and timestamp != self.foreign_warned_ticker_times.get(ticker):
                if price_return is not None:
                    price_change_text = f"(tăng {price_return:.2f}%)" if price_return > 0 else f"(giảm {abs(price_return):.2f}%)"
                else:
                    price_change_text = ""  # Không có dữ liệu hôm qua thì không hiển thị gì
                msg = (f"📉 <b>CẢNH BÁO: {ticker}</b>\n"
                    f"- NĐTNN <b>bán ra mạnh</b>: {abs(FNet) / 1_000_000:.2f} triệu VND trong 1'\n"
                    f"- <b>Giá đóng cửa:</b> {close_price:.0f} {price_change_text}\n"
                    f"- <b>Thời gian</b>: {timestamp}")
                self.foreign_warned_ticker_times[ticker] = timestamp  # Lưu ticker đã cảnh báo
                print(msg)
 
                self.foreign_telegram_notifier.send_message(msg)
 
        # Cảnh báo với BUSD
        if BUSD > 10000:  # Mua mạnh
            if BUSD > self.Config["N"] * BUSDPrev and BUSD > 1.3*BUSDMax and timestamp != self.busd_warned_ticker_times.get(ticker):
                print(f'Các mã đã cảnh báo: {self.busd_warned_ticker_times}')
                # Format lại price_return để chỉ hiển thị tăng/giảm %
                if price_return is not None:
                    price_change_text = f"(tăng {price_return:.2f}%)" if price_return > 0 else f"(giảm {abs(price_return):.2f}%)"
                else:
                    price_change_text = ""  # Không có dữ liệu hôm qua thì không hiển thị gì
                msg = (f"- <b>📈 {ticker} - MUA CHỦ ĐỘNG tăng mạnh </b>\n"
                       f"- <b>Giá đóng cửa:</b> {close_price:.0f} {price_change_text}\n"
                       f"- BU-SD = {BUSD / 1_000:.2f} nghìn CP trong 1'\n"
                       f"- <b>Tương quan BU/SD</b>: {BUSDratio:.2f} lần \n"
                       f"- <b>Thời gian</b>: {timestamp}")
                self.busd_warned_ticker_times[ticker] = timestamp
                print(msg)
                self.busd_telegram_notifier.send_message(msg)
       
        elif BUSD < -10000:  # Bán mạnh
            if BUSD < self.Config["N"] * BUSDPrev and BUSD < 1.3*BUSDMin and timestamp != self.busd_warned_ticker_times.get(ticker):
                print(f'Các mã đã cảnh báo: {self.busd_warned_ticker_times}')
                if price_return is not None:
                    price_change_text = f"(tăng {price_return:.2f}%)" if price_return > 0 else f"(giảm {abs(price_return):.2f}%)"
                else:
                    price_change_text = ""  # Không có dữ liệu hôm qua thì không hiển thị gì
                msg = (f"- <b>📉 {ticker} BÁN CHỦ ĐỘNG tăng mạnh </b>\n"
                       f"- BU-SD = {-(BUSD) / 1_000:.2f} nghìn CP trong 1'\n"
                       f"- <b>Giá đóng cửa:</b> {close_price:.0f} {price_change_text}\n"
                       f"- <b>Tương quan SD/BU</b>: {1/BUSDratio:.2f} lần \n"
                       f"- <b>Thời gian</b>: {timestamp}")
                self.busd_warned_ticker_times[ticker] = timestamp
                print(msg)
 
                self.busd_telegram_notifier.send_message(msg)
   
    def run(self):
        """Chạy hệ thống cảnh báo."""
        self._fetch_realtime_data(self._process_data)
 
# ===== 4. HÀM GIAO TIẾP VỚI NGƯỜI DÙNG =====
def user_input():
    """Hàm lấy thông tin cấu hình từ người dùng."""
    VN30 = [
    'STB', 'FPT', 'MSN', 'HPG', 'EVF',
    'MWG', 'EIB', 'VHM', 'DBC', 'DGC',
    'HDB', 'SSI', 'TCB', 'MBB', 'ACB',
    'VTP', 'VCB', 'HCM', 'VPI', 'VPB',
    'SZC', 'VIX', 'CTG', 'BID', 'HAH',
    'DIG', 'LGC', 'DXG', 'POW', 'HDG',
    'VIC', 'HVN', 'VN30F1M', 'BMP', 'TPB',
    'KDC', 'BAF', 'PVS', 'YEG', 'HAG',
    'VNM', 'HSG', 'LPB', 'PDR','VRE',
    'VOS', 'SHB', 'NTP','TNH','HNG']
    default_params = {
        "timeframe": "1m", #timeframe 1'
        "N": 5, #lớn hơn 5 lần nến gần nhất.
        "X": 500 # lớn nhất trong 300 nến gần nhất
    }
 
    print("\n🚀 Chào mừng đến hệ thống cảnh báo GDNN theo THỜI GIAN THỰC của FIINQUANT 🚀\n")
    print(f"📌 Sử dụng tham số mặc định: {default_params}")
 
    use_default = input("Bạn có muốn dùng tham số mặc định không? (y/n): ").strip().lower() == "y"
   
    if not use_default:
        tickers = input("Nhập danh sách mã cổ phiếu (mặc định: VN30, phân tách bằng dấu phẩy): ").replace(' ', '').split(',')
        timeframe = input("Nhập khung thời gian (mặc định: 1m): ").strip() or default_params["timeframe"]
        N = int(input("Nhập số lần giá trị lớn hơn timeframe trước đó (mặc định: 5): ") or default_params["N"])
        X = int(input("Nhập số timeframe trung bình để so sánh (mặc định: 100): ") or default_params["X"])
    else:
        tickers = VN30
        timeframe = default_params["timeframe"]
        N, X = default_params["N"], default_params["X"]
        
 
    telegram_signal = input("Gửi tín hiệu Telegram? (y/n): ").strip().lower() == "y"
    #bot_token = input("Nhập BOT TOKEN Telegram: ") if telegram_signal else None
    #chat_id = input("Nhập Chat ID Telegram: ") if telegram_signal else None
    #thread_id = input("Nhập THREAD ID (nếu có): ") if telegram_signal else None
 
 
    # Khởi chạy cảnh báo
    ForeignWarning(tickers, timeframe, N, X).run()
 
# ===== 5. CHẠY CHƯƠNG TRÌNH =====
if __name__ == "__main__":
    user_input()
```
````
