# Hướng dẫn cấu hình FiinQuant MCP Server trên Claude Desktop

## 1. Tải Claude Desktop

Truy cập trang chủ chính thức của Claude để tải về phiên bản Claude Desktop phù hợp với hệ điều hành đang sử dụng (Windows, macOS hoặc Linux).

* Mở trình duyệt web và truy cập địa chỉ: <https://claude.com/download>
* Chọn đúng phiên bản tương ứng với hệ điều hành của bạn (Windows / macOS / Linux).
* Tiến hành cài đặt theo hướng dẫn của trình cài đặt cho đến khi hoàn tất.

## 2. Mở cài đặt Connectors

Truy cập vào phần cài đặt connector của Claude Desktop:

* Mở **Settings** (Cài đặt) trong Claude Desktop.
* Điều hướng đến mục **Connectors**.
* Chọn **Customize** để mở danh sách connector tùy chỉnh.

<figure><img src="/files/A87gIU0HuooznDXFibIA" alt=""><figcaption></figcaption></figure>

## 3. Thêm Custom Connector mới

Trong giao diện Customize, tiến hành thêm connector mới:

* Ấn vào nút dấu cộng **"+"** để mở menu thêm mới.
* Chọn **"Add custom connector"** để bắt đầu tạo connector tùy chỉnh.

<figure><img src="/files/vyWrAX4rTWf0Z97UxiIB" alt=""><figcaption></figcaption></figure>

## 4. Điền thông tin Connector

Nhập các thông tin sau vào biểu mẫu Add custom connector:

<table><thead><tr><th width="188">Thông số</th><th>Giá trị</th></tr></thead><tbody><tr><td>Name</td><td>FiinQuant MCP</td></tr><tr><td>URL</td><td><a href="https://fiinquant-mcp.fiingroup.vn/mcp">https://fiinquant-mcp.fiingroup.vn/mcp</a></td></tr><tr><td>ClientID</td><td>FiinQuant.Web.Front.Client</td></tr></tbody></table>

Sau khi điền xong, ấn nút **"Add"** để lưu connector.

{% hint style="info" %}
**Mẹo:** Hãy kiểm tra kỹ URL trước khi ấn Add — đảm bảo giao thức `https://` đầy đủ và không có khoảng trắng thừa trong trường nhập liệu.
{% endhint %}

<figure><img src="/files/G1iiCeJq7p2UcE4DxQsV" alt=""><figcaption></figcaption></figure>

## 5. Kết nối với FiinQuant

Sau khi connector được thêm thành công:

* Ấn nút **"Connect"** bên cạnh connector vừa tạo.
* Hệ thống sẽ tự động **redirect** (chuyển hướng) sang trang **FiinQuant Authentication** để thực hiện xác thực.

<figure><img src="/files/ELO3yigviIdWyxpwzzrr" alt=""><figcaption></figcaption></figure>

> ***Lưu ý:** Trang FiinQuant Authentication sẽ mở trong trình duyệt mặc định. Nếu không thấy trang xuất hiện, hãy kiểm tra xem trình duyệt có chặn pop-up không và cho phép trang hiển thị.*

## 6. Đăng nhập tài khoản FiinQuant

Tại trang FiinQuant Authentication, thực hiện đăng nhập:

* Điền **tài khoản** (username/email) đã được đăng ký với FiinQuant.
* Điền **mật khẩu** tương ứng.
* Ấn **Đăng nhập** để hoàn tất xác thực.

<figure><img src="/files/13vXMZ05lSbEalJbVSb7" alt=""><figcaption></figcaption></figure>

## 7. Kích hoạt MCP trong conversation

Sau khi Claude Desktop khởi động lại, cần kích hoạt connector trong cuộc hội thoại:

* Tạo một **conversation mới**.
* Ở thanh chat phía dưới, ấn vào nút dấu cộng **"+"** để mở menu các công cụ.
* Chọn **Connectors**.
* Đảm bảo **FiinQuant MCP** được **toggle on** (bật).

<figure><img src="/files/uHdNg7k3H4ygc6uIntqs" alt=""><figcaption></figcaption></figure>
