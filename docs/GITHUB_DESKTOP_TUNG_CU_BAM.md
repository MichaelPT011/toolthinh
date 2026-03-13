# Huong dan GitHub Desktop tung cu bam

Tai lieu nay danh cho ban khi ban muon:

- dua source code len GitHub lan dau
- moi lan sua xong thi day len GitHub
- tu chay workflow de tao ban moi va auto update

Repo chinh thuc cua ban la:

```text
MichaelPT011/toolthinh
```

Link auto update da khoa san trong app la:

```text
https://raw.githubusercontent.com/MichaelPT011/toolthinh/main/latest.json
```

## A. Publish repo lan dau

### 1. Tao repo tren web GitHub

1. Mo trinh duyet.
2. Vao [https://github.com](https://github.com)
3. Dang nhap tai khoan GitHub cua ban.
4. O goc phai tren, bam dau `+`.
5. Bam `New repository`.
6. O o `Repository name`, go:

```text
toolthinh
```

7. Chon `Public`.
8. Khong tick them file README neu GitHub hoi.
9. Bam `Create repository`.

### 2. Mo repo local trong GitHub Desktop

1. Mo GitHub Desktop.
2. O thanh menu tren cung, bam `File`.
3. Bam `Add local repository...`
4. Bam `Choose...`
5. Chon thu muc:

```text
G:\Tool veo\veo3-safe-clone-release
```

6. Bam `Add repository`.

### 3. Publish len GitHub

1. Sau khi repo da mo trong GitHub Desktop, nhin goc tren ben phai.
2. Bam nut `Publish repository`.
3. O hop thoai hien ra:
   - `Name`: de `toolthinh`
   - bo tick `Keep this code private`
4. Bam `Publish repository`.

Neu GitHub Desktop khong publish vao dung repo ban vua tao, khong sao. Ban van co the:

1. Vao `Repository`
2. Bam `Repository settings...`
3. O muc `Remote`, sua URL thanh:

```text
https://github.com/MichaelPT011/toolthinh.git
```

4. Bam `Save`

## B. Bat quyen de workflow tu build va tu cap nhat latest.json

1. Mo repo `toolthinh` tren web GitHub.
2. Bam tab `Settings`.
3. O menu ben trai, tim `Actions`.
4. Bam `General`.
5. Keo xuong muc `Workflow permissions`.
6. Chon `Read and write permissions`.
7. Bam `Save`.

Neu khong bat muc nay, workflow se khong tu cap nhat `latest.json`.

## C. Moi lan ban sua app xong thi bam gi

### 1. Nho Codex sua

Ban chi can noi:

```text
Mo project G:\Tool veo\veo3-safe-clone-release
Sua loi sau: ...
Sua xong hay test lai va tang version giup toi.
```

### 2. Kiem tra file version

File can tang la:

[version.json](/G:/Tool%20veo/veo3-safe-clone-release/version.json)

Vi du:

```json
{
  "version": "2026.03.13.2",
  "channel": "stable",
  "name": "Tool Veo3's Thinh"
}
```

Tang thanh:

```json
{
  "version": "2026.03.13.3",
  "channel": "stable",
  "name": "Tool Veo3's Thinh"
}
```

### 3. Commit trong GitHub Desktop

1. Quay lai GitHub Desktop.
2. O cot ben trai, ban se thay danh sach file vua doi.
3. O o `Summary (required)`, go ten ngan gon. Vi du:

```text
Fix tao anh 4K va browser auto-download
```

4. O o `Description` co the de trong.
5. Bam nut xanh `Commit to main`.

### 4. Push len GitHub

1. Sau khi commit xong, nhin goc tren ben phai.
2. Bam `Push origin`.

Den day source cua ban da len GitHub.

## D. Chay workflow tao ban moi

1. Mo repo tren web GitHub.
2. Bam tab `Actions`.
3. O cot ben trai, bam workflow `Build and Release`.
4. O ben phai, bam `Run workflow`.
5. Chon branch `main`.
6. Bam nut xanh `Run workflow`.

## E. Theo doi workflow co xong chua

1. Van trong tab `Actions`.
2. Bam vao dong workflow vua chay.
3. Ban se thay 3 job:
   - `build-windows`
   - `build-macos`
   - `publish`
4. Cho den khi ca 3 job deu xanh.

Neu job do mau do, bam vao job do de copy loi gui cho Codex.

## F. Lay file de gui cho user

Sau khi workflow xong:

1. Vao tab `Releases` tren repo GitHub.
2. Mo release moi nhat.
3. Ban se thay file:
   - `Tool-Veo3s-Thinh-win.zip`
   - `Tool-Veo3s-Thinh-mac.zip`
4. Gui dung file zip phu hop cho user.

## G. User cua ban se update ra sao

Ban khong can bat ho lam gi voi GitHub.

User chi can:

1. mo app
2. app tu check ban moi khi mo len
3. neu co ban moi thi bam dong y cap nhat

## H. Neu GitHub Desktop bao loi push

Neu push loi:

1. chup anh loi
2. copy nguyen thong bao loi
3. gui lai cho Codex kem cau:

```text
Day la loi GitHub Desktop cua toi. Hay sua triet de trong project nay va huong dan toi bam tiep.
```

## I. Cach nho ngan gon nhat

Moi lan ra ban moi, ban chi can nho 5 viec:

1. nho Codex sua
2. tang version
3. Commit to main
4. Push origin
5. Run workflow
