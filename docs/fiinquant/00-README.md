# FiinQuant Documentation

FiinQuant – Thư viện dữ liệu và công cụ phân tích dành cho Python

## Giới thiệu

FiinQuant là **thư viện dữ liệu và công cụ phân tích** dành cho **Python**, giúp các nhà đầu tư, nhà phân tích và lập trình viên dễ dàng truy cập, xử lý và phân tích dữ liệu tài chính một cách nhanh chóng và chính xác.

### Các tính năng chính

1. **Nhận dữ liệu quá khứ**: Cho phép truy cập và lấy dữ liệu từ nhà cung cấp dữ liệu tài chính.

2. **Nhận dữ liệu khớp lệnh thời gian thực**: Cung cấp khả năng nhận dữ liệu thời gian thực, giúp theo dõi thị trường và cập nhật thông tin liên tục.

3. **Nối dữ liệu quá khứ và dữ liệu thời gian thực**: Thư viện cho phép gọi phương thức nối dữ liệu lịch sử từ thời gian cụ thể vào với dữ liệu thời gian thực theo các bước thời gian (timeframe) khác nhau.

4. **Tạo chỉ báo kỹ thuật**: Cung cấp các công cụ để xây dựng và tính toán các chỉ báo kỹ thuật từ đơn giản như giá trị các đường trung bình (SMA, EMA,...) đến phức tạp hơn như RSI (Relative Strength Index), MACD (Moving Average Convergence Divergence), Ichimoku và nhiều chỉ báo khác.

## Đặc điểm nổi bật

### Dữ liệu giao dịch nguồn chính thống
FiinQuant tích hợp trực tiếp dữ liệu thị trường từ các sở giao dịch (HOSE, HNX, UPCOM) theo thời gian thực, đảm bảo tính chính xác, minh bạch và đáng tin cậy cho các ứng dụng phân tích, giao dịch và nghiên cứu.

### Kết nối WebSocket realtime
FiinQuant hỗ trợ kết nối WebSocket ổn định và hiệu suất cao, cho phép:
- Nhận dữ liệu tick-by-tick hoặc cập nhật theo batch (VD: 1s, 5s, 1min)
- Push dữ liệu tự động vào dashboard, bot, hệ thống cảnh báo
- Đồng bộ liên tục với dữ liệu lịch sử để phục vụ các hệ thống phức tạp
- Websocket tích hợp cho module giá lẫn module sổ lệnh

### Dữ liệu tổng hợp sẵn theo từng phút
Hệ thống hỗ trợ dữ liệu tick by tick cho đến từng phút với đầy đủ timeframe 1' 5' 15' 1h 4h 1D cho phép người dùng gọi trực tiếp, không cần duy trì hệ thống server để lưu các dữ liệu lịch sử

### Sẵn sàng kết hợp dữ liệu lịch sử và realtime
FiinQuant cung cấp sẵn các hàm merge và đồng bộ dữ liệu lịch sử và realtime, giúp việc phát triển chiến lược, kiểm thử mô hình (backtest) và triển khai giao dịch dễ dàng và mượt mà.

### Dữ liệu dòng tiền thông minh – realtime & lịch sử
Bao gồm các chỉ báo chủ động như:
- BU-SD: Giá trị mua bán ròng của nhà đầu tư tổ chức/chủ động.
- NĐTNN: Hoạt động của nhà đầu tư nước ngoài realtime và theo chuỗi thời gian.

=> Hữu ích cho việc xác định dòng tiền lớn và xu hướng thị trường ngắn hạn – trung hạn.

### Tích hợp bộ chỉ báo phân tích kỹ thuật (TA) phổ biến
Thư viện tích hợp sẵn các bộ chỉ báo như:
- MA, EMA, RSI, MACD, Bollinger Bands
- Breakout Signals, Divergence
- Volume Profile và các nhóm chỉ báo hành vi thị trường

### Hàm tài chính nâng cao dành cho nhà đầu tư chuyên nghiệp
FiinQuant cung cấp nhiều hàm tiện ích sẵn sàng triển khai:
- Stock prediction: Dự báo xu hướng giá cổ phiếu bằng ML
- Similar chart: Tìm kiếm cổ phiếu có mô hình tương đồng
- Rebalance index: Tái cơ cấu danh mục chỉ số theo định kỳ hoặc tín hiệu
- Factor models: Phân tích yếu tố ảnh hưởng đến hiệu suất cổ phiếu
- Cập nhật định kỳ liên tục các mô hình tài chính khác

> Sử dụng thư viện FiinQuant không đơn thuần là công cụ truy xuất dữ liệu, còn là sử dụng hệ sinh thái các công cụ định lượng được xây dựng sẵn dành cho các nhà đầu tư.

## Tài liệu tham khảo

- Tài liệu chính thức: https://docs.fiinquant.vn/
- Danh sách đầy đủ: https://docs.fiinquant.vn/llms.txt
- Website FiinQuant: https://fiinquant.vn/

## Liên hệ & Hỗ trợ

- Email: info@fiinquant.vn
- Điện thoại: (+84) 886 911 000
- Địa chỉ: Tầng 10, Peakview Tower, 36 Hoàng Cầu, Ô Chợ Dừa, Hà Nội, Việt Nam

### Kênh liên lạc
- Facebook: https://www.facebook.com/FiinTradePlatform.official
- Telegram: https://t.me/canhbaolenh
- Zalo: https://zalo.me/0886911000
