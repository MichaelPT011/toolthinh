# Phat Hanh Bang GitHub Releases

Day la cach don gian nhat de ban phat hanh app va de ban be tu dong cap nhat moi khi mo app.

Luu y: app hien da khoa san nguon cap nhat chinh thuc tai:

```text
https://raw.githubusercontent.com/MichaelPT011/toolthinh/main/latest.json
```

Vi vay ban can phat hanh dung vao repo:

```text
MichaelPT011/toolthinh
```

## 1. Tao repo GitHub

- Tao hoac dung repo public `toolthinh` trong tai khoan `MichaelPT011`.
- Day toan bo thu muc app len repo nay.
- Vao `Settings -> Actions -> General -> Workflow permissions` va chon `Read and write permissions`.

## 2. Link cap nhat da co dinh san

App da duoc hardcode san link:

```text
https://raw.githubusercontent.com/MichaelPT011/toolthinh/main/latest.json
```

Ban khong can cho user nhap tay trong Cai dat nua.

## 3. Moi lan phat hanh ban moi

1. Sua `version.json` thanh version moi.
2. Commit va push code len GitHub.
3. Vao tab `Actions` tren GitHub.
4. Chay workflow `Build and Release`.

Workflow se tu dong:

- build ban Windows `.exe`
- build ban macOS `.app`
- zip 2 ban phat hanh
- tao GitHub Release moi
- cap nhat file `latest.json` o nhanh `main`
- tao hoac cap nhat GitHub Release voi 2 file zip Windows/macOS

## 4. Ban be cap nhat

Neu app cua ban be da duoc cai `Link latest.json`, moi lan mo app:

- app se tu check version moi
- neu co ban moi, app hoi xac nhan
- bam dong y la app tu tai, tu cap nhat, tu mo lai

## 5. Luu y

- Ban Windows va macOS khong build cheo duoc. Windows build tren Windows, macOS build tren macOS runner.
- Workflow GitHub da lam san phan nay cho ban.
- Neu repo dang private, auto-update se phuc tap hon. Repo public la de nhat.
