# Hướng Dẫn Public GitHub Và Auto Update Cho Tool Veo3 Của Thịnh

Tài liệu này dành cho người không biết code. Bạn chỉ cần làm đúng từng bước là app của bạn bè sẽ tự cập nhật mỗi khi bạn ra bản mới.

## Mục tiêu cuối cùng

Sau khi làm xong:

- bạn sửa app trên máy bạn bằng Codex
- bạn đưa bản mới lên GitHub
- bạn bè của bạn chỉ cần mở app
- app sẽ tự kiểm tra bản mới và hỏi cập nhật

## Lưu ý rất quan trọng

Bản app hiện tại đã được khóa sẵn nguồn cập nhật chính thức là:

```text
https://raw.githubusercontent.com/MichaelPT011/toolthinh/main/latest.json
```

Điều đó có nghĩa là:

- bạn không cần cho user nhập link cập nhật nữa
- nhưng bạn phải phát hành bản mới đúng vào repo GitHub:

```text
MichaelPT011/toolthinh
```

Nếu bạn đổi sang repo khác, app sẽ không nhận bản cập nhật đó.

## Phần 1. Chuẩn bị

Bạn cần có:

- 1 tài khoản GitHub
- 1 máy đang chứa source app này
- GitHub Desktop đã cài sẵn

Nếu chưa có GitHub Desktop:

- tải tại: [https://desktop.github.com](https://desktop.github.com)

## Phần 2. Đưa project lên GitHub lần đầu

### Bước 1. Tạo repo đúng

1. Mở GitHub trên web
2. Bấm `New repository`
3. Repo phải có đúng tên:

```text
toolthinh
```

4. Chọn `Public`
5. Bấm `Create repository`

### Bước 2. Đưa project local lên repo

1. Mở GitHub Desktop
2. Bấm `Add an Existing Repository from your local drive`
3. Chọn thư mục:

```text
G:\Tool veo\veo3-safe-clone-release
```

4. Nếu GitHub Desktop báo thư mục chưa là git repo, bấm tạo repo local
5. Sau đó bấm `Publish repository`
6. Chọn đúng repo:

```text
MichaelPT011/toolthinh
```

## Phần 3. Bật quyền để GitHub tự build và tự release

1. Vào repo của bạn trên GitHub
2. Vào:

```text
Settings -> Actions -> General
```

3. Ở phần `Workflow permissions`, chọn:

```text
Read and write permissions
```

4. Bấm `Save`

Đây là bước rất quan trọng. Nếu không bật, workflow sẽ không tự cập nhật `latest.json` và không tự tạo release đúng cách.

## Phần 4. Auto update đã được khóa sẵn

Bạn không cần nhập link `latest.json` trong app nữa.

App đã tự đọc đúng link này:

```text
https://raw.githubusercontent.com/MichaelPT011/toolthinh/main/latest.json
```

Việc của bạn chỉ là đảm bảo mỗi bản phát hành mới đều được đưa đúng lên repo đó.

## Phần 5. Mỗi lần bạn sửa app xong thì làm gì

Đây là quy trình chuẩn mỗi lần ra bản mới.

### Bước 1. Nhờ Codex sửa

Ví dụ bạn nói với Codex:

```text
Mở project này và sửa giúp tôi:
G:\Tool veo\veo3-safe-clone-release

Lỗi hiện tại:
- tạo ảnh 4K bị fail
- batch video chọn 4 output chỉ ra 2 file

Sửa xong hãy test lại và build lại bản phát hành nếu cần.
```

### Bước 2. Tăng version

Nhờ Codex sửa file:

```text
G:\Tool veo\veo3-safe-clone-release\version.json
```

Ví dụ:

```json
{
  "version": "2026.03.13.2",
  "channel": "stable",
  "name": "Tool Veo3's Thinh"
}
```

thành:

```json
{
  "version": "2026.03.13.3",
  "channel": "stable",
  "name": "Tool Veo3's Thinh"
}
```

Chỉ cần tăng số cuối là đủ.

### Bước 3. Commit và push

1. Mở GitHub Desktop
2. Ở ô `Summary`, gõ ví dụ:

```text
Fix loi tao anh 4K va batch video
```

3. Bấm:

```text
Commit to main
```

4. Bấm:

```text
Push origin
```

### Bước 4. Chạy workflow build/release

1. Lên GitHub web
2. Vào tab:

```text
Actions
```

3. Chọn workflow:

```text
Build and Release
```

4. Bấm:

```text
Run workflow
```

## Phần 6. Workflow sẽ tự làm gì

Bạn không cần tự build bằng tay.

Workflow hiện có sẵn trong project sẽ tự:

- build bản Windows
- build bản macOS
- tạo file zip phát hành
- tạo GitHub Release
- cập nhật `latest.json`

File workflow nằm ở:

```text
G:\Tool veo\veo3-safe-clone-release\.github\workflows\release.yml
```

## Phần 7. Bạn bè cập nhật như thế nào

Khi bạn bè đã có link `latest.json` trong app:

1. Họ mở app
2. App tự check bản mới
3. Nếu có bản mới, app hỏi cập nhật
4. Họ chỉ cần bấm đồng ý

Không cần họ biết GitHub, terminal hay code.

## Phần 8. Cách đơn giản nhất để bạn nhớ

Mỗi lần ra bản mới chỉ có 5 việc:

1. Nhờ Codex sửa
2. Tăng `version.json`
3. Commit
4. Push
5. Vào GitHub bấm `Run workflow`

## Phần 9. Mẫu câu bạn có thể gửi cho Codex mỗi lần muốn ra bản mới

```text
Mở project G:\Tool veo\veo3-safe-clone-release

Sửa các lỗi sau:
- ...
- ...

Sau khi sửa:
- test lại
- tăng version
- kiểm tra workflow release
- chuẩn bị để tôi chỉ cần commit, push và run workflow
```

## Phần 10. Nếu bạn muốn ít thao tác hơn nữa

Về sau bạn có thể nhờ Codex làm tiếp:

- tự cập nhật version cho bạn
- tạo sẵn nội dung commit
- tạo checklist phát hành
- tạo changelog bản mới

Như vậy bạn gần như chỉ còn việc bấm `Commit`, `Push`, `Run workflow`.
