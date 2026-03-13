# Hướng Dẫn Fix Phần Mềm Bằng Codex Cho Người Không Biết Code

Mục tiêu của tài liệu này là để sau khi bạn gửi phần mềm cho bạn bè, bạn vẫn có thể tự sửa lỗi và ra bản mới mà không cần biết lập trình.

## 1. Khi nào cần sửa

Bạn chỉ cần mở Codex khi gặp một trong các trường hợp sau:

- App báo lỗi khi tạo ảnh hoặc video
- Một nút bấm không hoạt động đúng
- Giao diện hiển thị xấu hoặc lệch
- Cần thêm tính năng mới
- Cần build bản cập nhật mới cho bạn bè

## 2. Bạn cần chuẩn bị gì

- Thư mục project gốc của app trên máy bạn
- Mô tả lỗi càng cụ thể càng tốt
- Nếu có thể, chụp ảnh lỗi hoặc ghi lại đúng câu báo lỗi

## 3. Cách nói chuyện với Codex để sửa

Bạn chỉ cần nói bằng ngôn ngữ bình thường.

Mẫu đơn giản:

```text
Mở project này và sửa lỗi giúp tôi:
- Khi tạo ảnh 4K thì bị failed
- Tôi muốn nút progress màu xanh lá
- Sau khi sửa hãy test lại toàn bộ
```

Mẫu tốt hơn:

```text
Mở project ở đường dẫn này và sửa giúp tôi:
G:\Tool veo\veo3-safe-clone-release

Lỗi hiện tại:
- Tab Ảnh Flow tạo 2K được nhưng 4K failed
- Batch video chọn 4 output nhưng chỉ ra 2 file

Yêu cầu:
- Sửa dứt điểm
- Test thật lại
- Nếu build cần cập nhật thì build lại luôn
```

## 4. Khi bạn của bạn báo lỗi

Hãy làm đúng thứ tự này:

1. Bảo bạn của bạn gửi ảnh lỗi hoặc video quay màn hình.
2. Hỏi họ bấm ở tab nào, chọn gì, nhập gì.
3. Hỏi họ đang dùng bản nào.
4. Copy nguyên mô tả đó vào Codex.

Mẫu nhắn cho Codex:

```text
Bạn tôi đang dùng app bản 2026.03.xx.
Lỗi xảy ra như sau:
- Vào tab Video
- Chọn Từ 1 ảnh
- Bấm Tạo ngay bây giờ
- App đứng ở 12% rồi failed

Hãy sửa trong source, test lại và build bản mới giúp tôi.
```

## 5. Sau khi Codex sửa xong bạn cần làm gì

Thông thường chỉ cần 3 việc:

1. Chạy thử bản mới trên máy bạn
2. Build bản phát hành mới
3. Đưa bản mới lên GitHub Releases để app của bạn bè tự cập nhật

## 6. Câu lệnh/yêu cầu nên dùng với Codex

### Khi cần sửa lỗi

```text
Sửa lỗi này giúp tôi và test lại thật kỹ.
Nếu phải đổi logic để ổn định hơn thì cứ làm.
```

### Khi cần thêm tính năng

```text
Thêm tính năng này vào app của tôi, thiết kế sao cho người dùng dễ hiểu nhất, rồi test lại toàn bộ.
```

### Khi cần ra bản mới

```text
Build lại bản Windows và macOS cho tôi.
Cập nhật latest.json và chuẩn bị sẵn để tôi đưa lên GitHub Releases.
```

## 7. Cách ra bản cập nhật cho bạn bè

Sau khi Codex sửa xong:

1. Bảo Codex build bản mới
2. Bảo Codex cập nhật `version.json`
3. Upload file zip mới lên GitHub Release
4. Cập nhật `latest.json`

Nếu app của bạn bè đã có link `latest.json`, lần sau họ chỉ cần mở app là app sẽ tự kiểm tra cập nhật.

## 8. Điều quan trọng nhất

Bạn không cần biết code.

Bạn chỉ cần nói rõ:

- đang lỗi ở đâu
- bạn muốn kết quả cuối cùng là gì
- muốn Codex sửa xong thì test gì

Phần còn lại để Codex làm.
