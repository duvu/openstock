# Hướng dẫn cài đặt FiinQuant MCP Server trên ChatGPT

## 1. Bật chế độ nhà phát triển

Truy cập vào phần cài đặt ứng dụng của ChatGPT để bật chế độ nhà phát triển:

* Mở **Settings** (Cài đặt) trong ChatGPT.
* Vào mục **Apps** (Ứng dụng).
* Chọn **Advanced settings** (Cài đặt nâng cao).
* Bật **Developer mode** (Chế độ nhà phát triển).

> ***Lưu ý:** Chế độ nhà phát triển cho phép tạo và quản lý các MCP server tùy chỉnh. Nếu không bật, bạn sẽ không thấy tùy chọn tạo ứng dụng mới ở bước tiếp theo.*

<figure><img src="/files/e94krLHyMu4Lzz5VPG9Z" alt=""><figcaption></figcaption></figure>

## 2. Tạo ứng dụng mới

Sau khi đã bật chế độ nhà phát triển, ấn nút **Create app** (Tạo ứng dụng) để bắt đầu thêm MCP server mới.

<figure><img src="/files/Lxls7eCCsJ8nGTjbUk5g" alt=""><figcaption></figcaption></figure>

## 3. Điền thông tin MCP Server

Điền đầy đủ các thông tin sau vào biểu mẫu tạo ứng dụng:

<table><thead><tr><th width="197">Thông số</th><th>Giá trị</th></tr></thead><tbody><tr><td>Tên</td><td>FiinQuant MCP</td></tr><tr><td>Kết nối</td><td>Server URL (URL máy chủ)</td></tr><tr><td>URL</td><td><a href="https://fiinquant-mcp.fiingroup.vn/mcp">https://fiinquant-mcp.fiingroup.vn/mcp</a></td></tr><tr><td>Authentication</td><td>Chọn Advanced OAuth settings</td></tr><tr><td>OAuth Client ID (Mục Callback URL)</td><td>FiinQuant.Web.Front.Client</td></tr><tr><td>Token endpoint auth method</td><td>None</td></tr></tbody></table>

* Tick vào ô **"I understand and want to continue"** để xác nhận rằng bạn đồng ý với các điều khoản sử dụng.
* Ấn nút **"Create"** để hoàn tất việc tạo ứng dụng.

<figure><img src="/files/TWAw3cKgKfwtuVQRmtUV" alt=""><figcaption></figcaption></figure>

{% hint style="info" %}
**Mẹo:** Hãy kiểm tra kỹ URL trước khi ấn Tạo — đảm bảo giao thức `https://` đầy đủ và không có khoảng trắng thừa.
{% endhint %}

## 4. Đăng nhập qua OAuth

Sau khi ấn **"Create"**, màn hình sẽ pop up thông báo đăng nhập, chọn **"Sign in with FiinQuant MCP"** trong cửa sổ pop up.

<figure><img src="/files/GNj6aCgyvfdpMWIqyQNV" alt=""><figcaption></figcaption></figure>

## 5. Xác thực với FiinQuant

Hệ thống sẽ tự động chuyển hướng (redirect) sang trang **FiinQuant Authentication**:

* Điền **tài khoản** và **mật khẩu** đã được đăng ký với FiinQuant.
* Ấn **Đăng nhập** để hoàn tất xác thực.

> ***Lưu ý:** Sau khi đăng nhập thành công, hệ thống sẽ tự động chuyển bạn về ChatGPT và MCP server sẽ sẵn sàng để sử dụng.*

<figure><img src="/files/4VdYATZVnwfvUOQQ7hqa" alt=""><figcaption></figcaption></figure>

## 6. Cách sử dụng MCP trong ChatGPT

Sau khi cấu hình hoàn tất, tiến hành sử dụng FiinQuant MCP trong các cuộc hội thoại:

* Tạo một **conversation mới** trong ChatGPT.
* Ở thanh nhập liệu phía dưới, bấm vào nút dấu cộng **"+"**.
* Chọn **"Add"** (Thêm).
* Chọn **FiinQuant MCP** từ danh sách các connector.
* Sau khi được thêm, bạn có thể đặt câu hỏi liên quan đến dữ liệu tài chính và ChatGPT sẽ sử dụng FiinQuant MCP để truy xuất thông tin.

<figure><img src="/files/nWYKzG7jOS94ZRR7rlcb" alt=""><figcaption></figcaption></figure>

{% hint style="info" %}
**Mẹo sử dụng:** MCP cần được thêm vào từng conversation mới. Nếu cuộc hội thoại không phản hồi dữ liệu tài chính, hãy kiểm tra lại xem FiinQuant MCP đã được thêm vào conversation hiện tại chưa.
{% endhint %}
