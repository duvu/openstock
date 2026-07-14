# Danh sách các công cụ

FiinQuant MCP cung cấp các công cụ truy xuất, phân tích và xử lý dữ liệu thị trường chứng khoán Việt Nam, bao gồm dữ liệu giao dịch, định giá, tài chính doanh nghiệp, chỉ báo kỹ thuật, dòng tiền, phân ngành, sàng lọc cổ phiếu và các phân tích tùy chỉnh.

## 1. get\_trading\_data

Lấy dữ liệu giao dịch mới nhất hoặc lịch sử cho cổ phiếu, chỉ số thị trường, chỉ số ngành, hợp đồng tương lai hoặc chứng quyền có bảo đảm.

### Chi tiết

Tool này là nguồn chính để lấy giá giao dịch, bao gồm giá mở cửa, cao nhất, thấp nhất, đóng cửa, khối lượng và giá trị giao dịch. Có thể dùng để lấy giá mới nhất trong ngày hoặc chuỗi dữ liệu lịch sử theo ngày và intraday.

### Dữ liệu hỗ trợ

* Giá mở cửa, cao nhất, thấp nhất, đóng cửa
* Khối lượng giao dịch
* Giá trị giao dịch
* Dữ liệu mua/bán chủ động nếu có
* Dữ liệu nước ngoài mua, bán, ròng
* Dữ liệu theo ngày hoặc intraday: 1 phút, 5 phút, 15 phút, 30 phút, 1 giờ

### Prompt mẫu

* Giá đóng cửa mới nhất của FPT là bao nhiêu?
* Lấy dữ liệu OHLCV của HPG trong 30 phiên gần nhất.
* So sánh giá trị giao dịch của VNM và MWG trong tuần vừa rồi.
* Lấy dữ liệu intraday 5 phút của VNINDEX trong hôm nay.
* Diễn biến giá của SSI trong 3 tháng gần nhất như thế nào?

## 2. get\_basic\_info

Lấy thông tin cơ bản của doanh nghiệp niêm yết.

### Chi tiết

Tool này truy xuất các thông tin nhận diện doanh nghiệp như tên công ty, sàn niêm yết, ngành nghề và phân loại ICB.

### Dữ liệu hỗ trợ

* Mã cổ phiếu
* Tên công ty
* Sàn giao dịch
* Ngành
* Phân loại ICB
* Thông tin phân ngành theo cấp độ

### Prompt mẫu

* Cho tôi thông tin cơ bản của FPT.
* HPG thuộc ngành nào theo phân loại ICB?
* Lấy tên công ty, sàn niêm yết và ngành của VCB, BID, CTG.
* MWG đang được phân loại trong ngành nào?
* Danh sách thông tin cơ bản của các mã trong nhóm ngân hàng.

## 3. get\_equity\_snapshot

Lấy nhanh các chỉ tiêu thị trường phi tài chính tại một thời điểm cho danh sách cổ phiếu đã biết.

### Chi tiết

Tool này cung cấp snapshot về vốn hóa, tỷ lệ tự do chuyển nhượng, khối lượng lưu hành, room ngoại, beta và các chỉ tiêu giao dịch trung bình. Phù hợp khi cần lấy nhanh nhiều chỉ tiêu thị trường cho một danh sách mã cụ thể.

### Dữ liệu hỗ trợ

* Vốn hóa thị trường
* Giá đóng cửa snapshot
* Biến động giá 1 ngày, 1 tuần, 1 tháng, từ đầu năm
* Giá trị và khối lượng giao dịch trung bình
* Free float và free float ratio
* Số lượng cổ phiếu niêm yết/lưu hành
* Giao dịch nhà đầu tư nước ngoài
* Tỷ lệ sở hữu nước ngoài và room còn lại
* Beta, beta 6 tháng, beta 2 năm

### Prompt mẫu

* Lấy vốn hóa thị trường và beta của FPT, MWG, HPG.
* Room ngoại còn lại của VNM là bao nhiêu?
* So sánh free float ratio của VCB, BID và CTG.
* Cổ phiếu nào trong danh sách VN30 có vốn hóa lớn nhất?
* Lấy biến động giá 1 tháng và YTD của nhóm bán lẻ.

## 4. get\_financial\_statements

Lấy dữ liệu báo cáo tài chính của doanh nghiệp.

### Chi tiết

Tool này truy xuất dữ liệu báo cáo kết quả kinh doanh, bảng cân đối kế toán, lưu chuyển tiền tệ hoặc toàn bộ báo cáo tài chính theo năm và quý.

### Dữ liệu hỗ trợ

* Báo cáo kết quả kinh doanh
* Bảng cân đối kế toán
* Báo cáo lưu chuyển tiền tệ
* Doanh thu
* Lợi nhuận sau thuế
* Lợi nhuận sau thuế công ty mẹ
* EPS
* Dòng tiền từ hoạt động kinh doanh
* Các trường dữ liệu tài chính gốc từ FiinQuantX

### Prompt mẫu

* Doanh thu và lợi nhuận sau thuế của FPT trong Q1/2025 là bao nhiêu?
* Lấy báo cáo kết quả kinh doanh của HPG trong 5 năm gần nhất.
* So sánh lợi nhuận sau thuế của MWG năm 2024 và 2023.
* Dòng tiền hoạt động kinh doanh của VNM trong Q4/2024 là bao nhiêu?
* Lấy bảng cân đối kế toán của VCB trong các quý năm 2025.

## 5. get\_financial\_ratios

Lấy các chỉ số tài chính của doanh nghiệp.

### Chi tiết

Tool này truy xuất các chỉ số tài chính phổ biến theo năm hoặc quý, bao gồm khả năng sinh lời, hiệu quả hoạt động, đòn bẩy, định giá và các chỉ tiêu đặc thù ngành ngân hàng.

### Dữ liệu hỗ trợ

* ROE
* ROA
* EPS
* NIM
* CASA
* Tỷ lệ nợ xấu
* P/E
* P/B
* Các chỉ tiêu tài chính khác từ FiinQuantX

### Prompt mẫu

* ROE của FPT trong 5 năm gần nhất thay đổi như thế nào?
* So sánh ROA của VCB, BID và CTG trong năm 2024.
* NIM và CASA của TCB trong Q1/2025 là bao nhiêu?
* P/E hiện tại của MWG cao hay thấp so với các năm trước?
* Tỷ lệ nợ xấu của nhóm ngân hàng trong năm 2025 như thế nào?

## 6. get\_valuation\_metrics

Lấy dữ liệu định giá cho cổ phiếu, chỉ số hoặc ngành.

### Chi tiết

Tool này cung cấp các chỉ tiêu định giá theo phạm vi cổ phiếu, chỉ số hoặc ngành, hỗ trợ phân tích mức định giá hiện tại và lịch sử.

### Dữ liệu hỗ trợ

* Định giá cổ phiếu
* Định giá chỉ số
* Định giá ngành
* Dữ liệu lịch sử theo ngày
* Các chỉ tiêu như P/E, P/B hoặc các metric định giá khác tùy phạm vi dữ liệu

### Prompt mẫu

* Định giá P/E của VNINDEX hiện tại là bao nhiêu?
* So sánh P/B của VCB và BID trong 1 năm gần nhất.
* Ngành ngân hàng đang được định giá như thế nào?
* Lấy dữ liệu định giá của VN30 từ đầu năm đến nay.
* Cổ phiếu FPT đang giao dịch ở mức định giá nào so với lịch sử?

## 7. get\_market\_statistics

Lấy các thống kê thị trường cấp cổ phiếu.

### Chi tiết

Tool này dùng để truy xuất các thống kê thị trường như vốn hóa, giá trị giao dịch, khối lượng, dòng tiền nước ngoài, free float, dòng tiền theo nhóm nhà đầu tư, giao dịch tự doanh và dữ liệu trần/sàn.

### Dữ liệu hỗ trợ

* Vốn hóa thị trường
* Giá trị giao dịch
* Khối lượng giao dịch
* Dòng tiền nước ngoài
* Free float
* Dòng tiền theo nhóm nhà đầu tư
* Tự doanh
* Dữ liệu trần/sàn

### Prompt mẫu

* Lấy giá trị giao dịch của HPG trong 10 phiên gần nhất.
* Dòng tiền nước ngoài ở FPT trong tháng qua như thế nào?
* Thống kê khối lượng giao dịch của SSI từ đầu năm đến nay.
* Tự doanh mua bán ròng cổ phiếu nào trong danh sách ngân hàng?
* Vốn hóa thị trường của VNM thay đổi thế nào trong 6 tháng gần nhất?

## 8. get\_market\_breadth

Lấy dữ liệu độ rộng thị trường cho chỉ số.

### Chi tiết

Tool này cung cấp thống kê số mã tăng, giảm, đứng giá và các chỉ tiêu breadth cho một chỉ số như VNINDEX hoặc VN30.

### Dữ liệu hỗ trợ

* Số mã tăng
* Số mã giảm
* Số mã không đổi
* Độ rộng thị trường theo ngày, tuần, tháng, quý hoặc năm
* Dữ liệu breadth cho chỉ số

### Prompt mẫu

* Độ rộng thị trường VNINDEX hôm nay như thế nào?
* Có bao nhiêu mã tăng và giảm trong VN30 phiên gần nhất?
* So sánh breadth của VNINDEX trong tuần này và tuần trước.
* Thị trường có đang lan tỏa tích cực không?
* Lấy dữ liệu số mã tăng giảm của VNINDEX trong 1 tháng gần nhất.

## 9. get\_money\_flow\_contribution

Phân tích đóng góp hoặc tác động kéo giảm của cổ phiếu lên chỉ số.

### Chi tiết

Tool này dùng để xác định các cổ phiếu đóng góp tích cực hoặc tiêu cực vào diễn biến của một chỉ số, đồng thời hỗ trợ phân tích xếp hạng dòng tiền hoặc tác động theo nhiều khung thời gian.

### Dữ liệu hỗ trợ

* Top cổ phiếu đóng góp tăng điểm
* Top cổ phiếu kéo giảm chỉ số
* Phân tích theo 1 ngày, 5 ngày, 10 ngày, 20 ngày
* Xếp hạng theo chỉ số như VNINDEX, VN30

### Prompt mẫu

* Cổ phiếu nào kéo VNINDEX giảm mạnh nhất hôm nay?
* Top 10 mã đóng góp tích cực nhất cho VN30 trong 5 ngày qua.
* Những cổ phiếu nào đang tác động tiêu cực đến VNINDEX?
* So sánh nhóm cổ phiếu kéo tăng và kéo giảm thị trường trong 20 ngày gần nhất.
* Hôm nay chỉ số tăng chủ yếu nhờ những mã nào?

## 10. get\_index\_constituents

Lấy danh sách cổ phiếu thành phần của một chỉ số hoặc rổ cổ phiếu.

### Chi tiết

Tool này trả về danh sách mã thuộc một chỉ số như VN30 hoặc các rổ chỉ số được hỗ trợ.

### Dữ liệu hỗ trợ

* Danh sách cổ phiếu thành phần
* Mã cổ phiếu trong chỉ số
* Rổ chỉ số hoặc basket

### Prompt mẫu

* Danh sách cổ phiếu trong VN30 gồm những mã nào?
* Lấy các mã thành phần của VNFINLEAD.
* Cho tôi danh sách cổ phiếu trong chỉ số VNDIAMOND.
* Những mã nào đang thuộc rổ VN30?
* Lấy danh sách constituent để phân tích định giá nhóm VN30.

## 11. get\_icb\_industries

Lấy danh sách ngành theo hệ thống phân loại ICB.

### Chi tiết

Tool này trả về tên ngành theo cấp độ ICB, hỗ trợ phân tích theo ngành hoặc xây dựng bộ lọc ngành cho screener.

### Dữ liệu hỗ trợ

* Danh sách ngành ICB
* Phân ngành theo level
* Tên ngành và mã ngành tương ứng

### Prompt mẫu

* Lấy danh sách ngành ICB cấp 2.
* Có những ngành ICB level 4 nào trong hệ thống?
* Mã ngành của nhóm ngân hàng là gì?
* Cho tôi danh sách phân ngành để dùng cho bộ lọc cổ phiếu.
* Ngành chứng khoán thuộc ICB level nào?

## 12. screen\_stocks

Sàng lọc cổ phiếu theo bộ tiêu chí tài chính, định giá, thanh khoản, ngành và thị trường.

### Chi tiết

Tool này dùng để lọc và xếp hạng cổ phiếu dựa trên các chỉ tiêu từ FiinQuantX StockScreening. Có thể kết hợp nhiều điều kiện như P/E, P/B, ROE, tăng trưởng doanh thu, vốn hóa, thanh khoản, beta, room ngoại hoặc ngành.

### Dữ liệu hỗ trợ

* Bộ lọc định giá
* Bộ lọc tăng trưởng
* Bộ lọc khả năng sinh lời
* Bộ lọc thanh khoản
* Bộ lọc vốn hóa
* Bộ lọc ngành ICB
* Bộ lọc theo sàn giao dịch
* Sắp xếp kết quả theo chỉ tiêu mong muốn

### Prompt mẫu

* Tìm các cổ phiếu có P/E dưới 12 và ROE trên 15%.
* Sàng lọc cổ phiếu vốn hóa lớn, thanh khoản cao, tăng trưởng doanh thu dương.
* Tìm các cổ phiếu ngành chứng khoán có P/B thấp nhất.
* Lọc cổ phiếu HOSE có room ngoại còn lại trên 20%.
* Tìm top 20 cổ phiếu có ROE cao nhất trong nhóm VNINDEX.

## 13. get\_technical\_indicators

Tính toán các chỉ báo kỹ thuật cho cổ phiếu hoặc chỉ số.

### Chi tiết

Tool này tính toán các chỉ báo kỹ thuật phổ biến dựa trên dữ liệu giá, hỗ trợ phân tích xu hướng, động lượng, dòng tiền và tín hiệu giao dịch.

### Chỉ báo hỗ trợ

* RSI
* MACD
* SMA
* EMA
* ADX
* MFI
* Supertrend
* MCDX
* Các chỉ báo FiinIndicator khác

### Dữ liệu hỗ trợ

* Chỉ báo theo ngày
* Chỉ báo intraday
* Dữ liệu điều chỉnh hoặc không điều chỉnh
* Giá trị mới nhất hoặc chuỗi lịch sử

### Prompt mẫu

* RSI 14 ngày của FPT hiện tại là bao nhiêu?
* Tính MACD của VNINDEX trong 6 tháng gần nhất.
* Cổ phiếu HPG có đang vượt SMA 50 không?
* Lấy tín hiệu Supertrend của MWG.
* So sánh RSI của SSI, VND và HCM.

## 14. detect\_pattern

Phát hiện mẫu hình kỹ thuật hoặc mô hình giá.

### Chi tiết

Tool này gọi các phương pháp nhận diện mẫu hình kỹ thuật như doji, engulfing, trendline hoặc hỗ trợ/kháng cự.

### Mẫu hình hỗ trợ

* Doji
* Engulfing
* Trendline
* Support/resistance
* Các pattern kỹ thuật được đăng ký trong hệ thống

### Prompt mẫu

* FPT có xuất hiện nến Doji gần đây không?
* Kiểm tra mẫu hình engulfing của HPG trong 30 phiên gần nhất.
* Tính vùng hỗ trợ và kháng cự của VNINDEX.
* Phát hiện trendline của cổ phiếu MWG.
* Mã SSI có tín hiệu đảo chiều kỹ thuật nào không?

## 15. get\_realtime\_bid\_ask

Lấy snapshot giá mua/bán realtime giới hạn.

### Chi tiết

Tool này lấy dữ liệu bid/ask realtime trong phiên giao dịch. Phù hợp khi cần quan sát trạng thái sổ lệnh hiện tại hoặc mức giá chào mua/chào bán gần nhất.

### Dữ liệu hỗ trợ

* Giá bid
* Giá ask
* Khối lượng bid/ask nếu có
* Snapshot realtime theo số lượng event giới hạn

### Prompt mẫu

* Lấy giá bid/ask realtime của FPT.
* Sổ lệnh hiện tại của HPG như thế nào?
* Kiểm tra giá chào mua và chào bán của SSI.
* Bid/ask của VN30F1M hiện tại ra sao?
* Có dữ liệu realtime cho MWG không?

## 16. get\_rrg\_analysis

Phân tích Relative Rotation Graph cho danh sách cổ phiếu so với benchmark.

### Chi tiết

Tool này dùng để phân tích vị thế tương đối của các cổ phiếu so với chỉ số tham chiếu, hỗ trợ nhận diện nhóm dẫn dắt, cải thiện, suy yếu hoặc tụt hậu.

### Dữ liệu hỗ trợ

* Phân tích RRG
* Benchmark mặc định VNINDEX
* Danh sách cổ phiếu tùy chọn
* Tham số phân tích bổ sung

### Prompt mẫu

* Phân tích RRG của FPT, MWG, HPG so với VNINDEX.
* Nhóm ngân hàng đang ở quadrant nào trên RRG?
* Cổ phiếu nào trong VN30 đang dẫn dắt thị trường?
* So sánh sức mạnh tương đối của SSI, VND và HCM.
* Những mã nào đang chuyển từ lagging sang improving?

## 17. get\_rebalance

Tính toán phân bổ danh mục theo chỉ số với một ngân sách nhất định.

### Chi tiết

Tool này hỗ trợ tính toán allocation hoặc tái cân bằng danh mục theo một chỉ số, ví dụ VN30, dựa trên ngân sách đầu tư cụ thể.

### Dữ liệu hỗ trợ

* Chỉ số mục tiêu
* Ngân sách đầu tư
* Số lượng phân bổ theo mã
* Gợi ý tỷ trọng hoặc giá trị đầu tư theo constituent

### Prompt mẫu

* Với 1 tỷ đồng, phân bổ theo rổ VN30 như thế nào?
* Tính rebalance danh mục VN30 với ngân sách 500 triệu.
* Tôi muốn mô phỏng danh mục theo chỉ số VN30.
* Với 2 tỷ đồng, nên mua bao nhiêu mỗi mã trong VN30?
* Tính allocation theo rổ VNDIAMOND nếu có dữ liệu hỗ trợ.
