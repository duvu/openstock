# Danh sách các phiên bản

## Version 0.1.60 (mới nhất) 🎉

### Tính năng mới
- Bổ sung dữ liệu số hợp đồng mở cho các mã phái sinh ở hàm phân loại giao dịch theo nhà đầu tư
  - Xem: [1.8. Lấy dữ liệu giao dịch theo nhà đầu tư](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban/1.8.-lay-du-lieu-giao-dich-theo-nha-dau-tu.md)

### Cải thiện
- Tối ưu hóa hiệu suất kết nối WebSocket
- Cập nhật bộ chỉ báo kỹ thuật

## Version 0.1.59

### Tính năng mới
- Bổ sung thêm các chỉ số TA mới
- Cải thiện xử lý dữ liệu realtime

## Version 0.1.53

### Tính năng mới
- Dữ liệu phân loại giao dịch theo nhà đầu tư
  - Xem: [1.8. Lấy dữ liệu giao dịch theo nhà đầu tư](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban/1.8.-lay-du-lieu-giao-dich-theo-nha-dau-tu.md)
- Dữ liệu bộ lọc cổ phiếu
  - Xem: [10. Bộ lọc cổ phiếu](/ham-va-cong-thuc/10.-bo-loc-co-phieu.md)

## Version 0.1.50

### Tính năng mới
- Dữ liệu lịch sử với giá trị giao dịch
  - Xem: [2.2. Hàm dữ liệu Lịch sử](/ham-va-cong-thuc/2.-du-lieu-giao-dich/2.2.-ham-du-lieu-lich-su.md)
- Dữ liệu Realtime kết hợp lịch sử với giá trị giao dịch
  - Xem: [2.3. Hàm nối dữ liệu Realtime và lịch sử](/ham-va-cong-thuc/2.-du-lieu-giao-dich/2.3.-ham-noi-du-lieu-realtime-va-lich-su.md)
- Dữ liệu vốn hóa và room NĐTNN realtime trong phiên giao dịch
  - Xem: [1.4. Lấy dữ liệu vốn hóa](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban/1.4.-lay-du-lieu-von-hoa.md)
  - Xem: [1.5. Lấy dữ liệu room NĐTNN](/ham-va-cong-thuc/1.-danh-muc-and-thong-tin-co-ban/1.5.-lay-du-lieu-room-ndtnn.md)

## Version 0.1.49

### Tính năng mới
- Các chỉ số TA mới:
  - Point of Control (POC)
  - Coppock Curve
  - Fibonacci

### Cải thiện
- Sửa tham số RRG - chỉ cần truyền đúng tham số `period` và `from_date`
- Hàm dữ liệu lịch sử thêm tính năng gọi dữ liệu sector index với timeframe 1D

## Changelog Lịch sử

### v0.1.48
- Bổ sung dữ liệu phái sinh
- Cải thiện API kết nối

### v0.1.47
- Tối ưu hóa hiệu suất
- Thêm hàm hỗ trợ mới

### Phiên bản cũ hơn
- Xem tại: https://docs.fiinquant.vn/tai-lieu-ki-thuat/danh-sach-cac-phien-ban.md

## Hướng dẫn cập nhật

```bash
pip install --upgrade --extra-index-url https://fiinquant.github.io/fiinquantx/simple fiinquantx
```

## Kiểm tra phiên bản hiện tại

```python
import fiinquantx
print(fiinquantx.__version__)
```
