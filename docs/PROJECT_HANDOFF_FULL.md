# Project Handoff Full

Tai lieu nay duoc viet de mot doi dev moi, chua biet gi ve project, van co the:

- doc hieu toan bo he thong
- review code
- tiep tuc phat trien
- build / release / hotfix
- debug khi user bao loi

Tai lieu nay phan anh trang thai du an tai thoi diem:

- ngay cap nhat: 2026-03-14
- version local: `2026.03.14.1`
- ten san pham: `Tool Veo3's Thinh`

## 1. Muc tieu san pham

Day la ung dung desktop PySide6 cho phep nguoi dung:

- dang nhap Google Flow/Labs bang browser that
- tao anh bang Flow
- tao video bang Flow / Veo
- tao hang loat prompt
- ghep video bang FFmpeg
- tu dong cap nhat ban moi
- dong goi cho user Windows, va co san quy trinh build cho macOS

Project khong dung:

- exported cookies
- API private / internal tRPC
- browser headless bot theo kieu fake API

Project hien tai chay theo huong:

- dung browser that + Playwright
- thao tac tren UI chinh thuc cua Flow
- uu tien tinh hop le, giam rui ro khoa tai khoan, giam rui ro thay doi private API

## 2. Trang thai he thong hien tai

### 2.1 Cac luong da chay duoc va da test live

Da test that tren Flow/Labs bang browser that:

- dang nhap profile Flow va doc email tu profile Chrome
- tao anh don
- tao anh nhieu output
- tao anh 2K
- tao anh tham chieu
- tao video tu prompt
- tao video tu 1 anh
- tao video tu anh dau va anh cuoi
- tao video tu thanh phan
- tao chuoi video `text -> extend -> extend`

Da test local / smoke:

- khoi dong app
- khoi tao UI chinh
- preset an toan duoc tick san
- button tao hang loat mac dinh dung text dung
- doc profile/email trong tab Tai khoan
- compileall pass

### 2.2 Cac diem da duoc gia co trong dot fix nay

- video tile khong con phu thuoc selector `play_circle` cu
- mo detail video bang link `/edit/...` lay truc tiep tu tile
- extend chain khong con doi upload video local
- extend download da xu ly menu 2 tang `Full Video -> chat luong`
- logic extend khong bi fail gia vi chu `Failed` trong lich su cu
- doc duoc email va ten user tu `Preferences` cua Chrome profile
- preset an toan duoc check san luc mo tab
- batch expand button chuyen mau xam khi mo
- startup auto-update da duoc doi sang popup chuan bi

### 2.3 Cac gioi han con lai

Khong nen xem day la loi code, ma la gioi han san pham / nen tang:

- Flow UI co the doi selector bat ky luc nao
- toc do render phu thuoc server Flow, khong phai may local
- 2K/4K co the xuat hien / bien mat tuy loai media va trang thai UI
- mot so menu download cua video / extend co cau truc khac nhau
- build macOS khong the build local tren Windows; can GitHub Actions hoac may Mac

## 3. Kien truc tong quan

Ung dung duoc chia 2 lop:

- `core/`: nghiep vu, automation, batch, update, project, ffmpeg
- `gui/`: PySide6 UI

Flow tong quan:

```text
User
  -> GUI tab
  -> Generator
  -> Automation
  -> Shared browser runtime
  -> Flow official UI
  -> Download file
  -> Save vao output/
```

## 4. Cau truc thu muc

```text
veo3-safe-clone-release/
├── assets/                     # icon, asset runtime/build
├── build/                      # output build local
├── chrome-win64/               # browser bundle neu co
├── core/                       # nghiep vu chinh
├── data/                       # du lieu runtime, settings, context, projects
├── docs/                       # tai lieu
├── gui/                        # PySide6 UI
├── output/                     # file tao ra
├── release/                    # zip phat hanh local
├── release_tools/              # script build/release
├── .github/workflows/          # GitHub Actions
├── bootstrap.py                # launcher helper / env bootstrap
├── latest.json                 # manifest update
├── main.py                     # entry point
├── requirements.txt
└── version.json
```

## 5. Module-by-module

## 5.1 `core/config.py`

Noi dinh nghia:

- ten app
- path runtime
- path output
- path profile / browser managed
- URL Flow / Labs
- default settings
- preset an toan cho tab Anh / Video
- official manifest update URL

File nay la single source of truth cho:

- app title
- output dir
- managed browser dirs
- update source

Neu doi ten app, doi url update, doi path quan ly browser, sua file nay truoc.

## 5.2 `core/browser_assist.py`

Trach nhiem:

- tim browser path
- tu dong tai browser neu may khong co Chrome
- mo browser dang nhap Flow
- mo tool URL bang browser that
- quan ly user-data-dir / profile-dir
- doc thong tin danh tinh tu profile Chrome
- theo doi downloads
- import file tu Downloads ve `output/`

### Diem quan trong

- `launch_login_browser()` mo dung URL Flow login:
  - `https://labs.google/fx/vi/tools/flow`
- `read_profile_identity()` doc:
  - email
  - user_name
  - profile_name
  tu file `Preferences`
- `wait_for_downloads()` theo doi file moi trong Downloads den khi on dinh

### Rui ro

Neu Chrome doi format file `Preferences`, phan doc email can cap nhat.

## 5.3 `core/browser_installer.py`

Muc dich:

- tu dong tai browser when needed
- dung cho user may moi, khong cai Chrome

Trang thai hien tai:

- Windows da co duong dan va smoke test
- macOS co luong build/release, nhung can test tren may Mac hoac GitHub runner Mac

## 5.4 `core/flow_runtime.py`

Day la lop rat quan trong.

Nhiem vu:

- khoi dong 1 persistent browser context
- mute audio
- an window khi user khong bat `show_browser_window`
- reuse 1 browser + nhieu tab
- gioi han so tab song song
- lock download de tranh hai job tranh nhau save file

### Ly do module nay quan trong

Neu khong co shared runtime:

- mo nhieu Chrome se nang may
- de xung dot profile
- de bi fail do browser lock

Shared runtime hien tai giup:

- 1 browser
- nhieu page/tab
- song song co kiem soat

## 5.5 `core/flow_automation.py`

Automation cho tab Anh.

Nhiem vu:

- mo Flow image project
- chon so anh
- chon ngang/doc
- khoa model ve `Nano Banana 2`
- nap anh tham chieu neu co
- submit prompt
- cho Flow render
- tai anh theo quality

### Chi tiet quan trong

- neu co `image_path` va user chon `2K/4K`, code ha ve `1080p`
- ly do: tren Flow, anh tham chieu thuong chi tai on dinh o 1080p
- day la fail-safe chu khong phai bug

### Download upscale

Image download co 2 truong hop:

1. Click xong la download ngay
2. Click xong bat dau upscale, can cho roi moi download

Code da xu ly ca 2 truong hop.

## 5.6 `core/video_automation.py`

Day la module phuc tap nhat hien tai.

Nhiem vu:

- tao video tu prompt
- tao video tu 1 anh
- tao video tu anh dau/cuoi
- tao video tu nhieu thanh phan
- keo dai video (extend chain)
- mo detail video
- tai video
- luu context project/detail de extend tiep

### Thiet ke hien tai

- video x2/x3/x4 cua Flow rat khong on dinh
- user van chon 1..4 output
- nhung backend thuc hien thanh nhieu lan x1
- muc tieu: on dinh hon selector x2/x3/x4 native cua Flow

### Video detail selector

Selector cu:

- click `play_circle`

Selector moi:

- doc tile link `a[href*="/edit/"]`
- mo thang URL detail
- fallback sang text `play_circle` neu can

### Extend chain

File context:

- [data/last_video_context.json]

No luu:

- `project_url`
- `detail_url`

Logic chain:

1. prompt 1 tao video goc
2. save `project_url` + `detail_url`
3. prompt 2 mode `extend` mo lai `detail_url`
4. click `Extend`
5. doi prompt moi
6. Flow render video keo dai
7. download full chain
8. cap nhat lai `detail_url`
9. prompt 3 extend tiep tu `detail_url` moi

### Diem kho nhat da sua

1. `Failed` xuat hien trong body khong phai luc nao cung la job hien tai fail.
   - Trong extend, lich su ben phai co the chua clip cu fail.
   - Vi vay `wait_for_extend_result()` khong duoc fail som chi vi thay chu `Failed`.

2. Download menu cua extend la menu 2 tang.
   - tang 1: `Full Video / Clip 1 / Clip 2 / Clip 3`
   - tang 2: `720p / Original Size / ...`
   - code cu doi download event o tang 1 nen timeout
   - code moi mo `Full Video` truoc, sau do moi chon quality

## 5.7 `core/google_auth.py`

Trong ban nay, module nay khong con la cookie auth engine nhu design cu.
No duoc chuyen thanh profile/account registry cuc bo.

No dung de:

- luu account local
- dong bo browser profile account
- doc / cap nhat email, user_name, nickname, proxy
- danh dau `active`

### Browser-managed account

Khi user dang nhap Flow qua browser cua app:

- `BrowserAssist.read_profile_identity()` doc email
- `GoogleAuth.sync_browser_profile_account()` tao/cap nhat ho so

Bang Tai khoan hien email do doc duoc tu browser profile.

## 5.8 `core/flow_gen.py`

Lop generator cho Anh.

Vai tro:

- tao job
- retry / status / error
- goi vao `FlowAutomation`
- tra ve job dict cho GUI / batch

## 5.9 `core/video_gen.py`

Lop generator cho Video.

Vai tro:

- retry toi da 10 lan
- goi `VideoAutomation`
- cap nhat progress/status
- tra ve job dict cho GUI / batch

### Retry behavior

Neu Flow fail bat on:

- tu retry den 10 lan
- luu `attempts`
- GUI hien text retry

## 5.10 `core/batch.py`

Batch engine cho ca anh va video.

Che do:

- `SEQUENTIAL`
- `PARALLEL`

### Co che song song

- reuse shared runtime theo generator type
- 1 browser, nhieu tab
- semaphore gioi han so task song song

### Extend batch

Logic batch extend khong map theo local video file.

Hien tai:

- dong 1: tao video goc (`mode=text`)
- dong 2..N: `mode=extend`

Can luu y:

- Extend bat buoc chay tuần tự
- Trong UI, khi mode `extend`, batch se force ve tuần tự / 1 concurrent

## 5.11 `core/concat.py`

Dung FFmpeg de:

- trim clip
- sync duration
- concat lai

Tang nay doc lap voi Flow.

## 5.12 `core/project.py`

CRUD project local.

Dung de:

- tao du an
- save state
- load state
- xoa du an

## 5.13 `core/environment_check.py`

Muc dich:

- giup support user may moi
- kiem tra browser
- kiem tra duong dan
- kiem tra output/download dir
- giup giam loi dau vao

Nen dung khi:

- user bao app khong tao duoc
- user moi cai may
- support tu xa

## 5.14 `core/updater.py`

Updater hien tai:

- check manifest `latest.json`
- so sanh version
- download zip release
- spawn process update
- restart app

### Dieu rat quan trong

Co che update khi app dang chay la noi de loi nhat.
Version hien tai da tranh bot crash bang cach:

- xu ly source root thong minh hon
- spawn updater rieng

Nhung team moi can rat can than khi dong vao updater.

## 6. GUI modules

## 6.1 `gui/main_window.py`

Vai tro:

- khoi tao tabs
- theme chung
- menu
- startup popup check update
- tool menu

Tabs hien tai:

- Video VEO3
- Anh Flow
- Ghep video
- Tai khoan
- Huong dan

## 6.2 `gui/account_tab.py`

Vai tro:

- mo browser dang nhap Flow
- hien email, ten user, profile browser
- table ho so
- validate / proxy / xoa ho so

### Hanh vi quan trong

Sau khi bam `Mo trinh duyet dang nhap Flow`:

- app mo browser o URL Flow
- bat timer poll identity
- khi user dang nhap xong, email se tu dong len bang

## 6.3 `gui/flow_tab.py`

Tinh nang:

- prompt anh
- so anh 1..4
- quality
- ngang/doc
- anh tham chieu
- preset an toan
- batch panel
- bang ket qua

## 6.4 `gui/video_tab.py`

Tinh nang:

- mode `text`
- mode `image`
- mode `start_end`
- mode `ingredients`
- mode `extend`
- quality
- output count
- ratio
- duration
- preset an toan
- batch panel

### Extend UI

Khong cho user upload local video.
Thay vao do:

- huong user tao chain prompt trong cung project
- batch logic tu map prompt 1 thanh create, prompt sau thanh extend

## 6.5 `gui/batch_widgets.py`

Inline batch panel.

Tinh nang:

- load prompt file
- them prompt
- load file sequence
- load root folder
- filter list
- retry tung dong
- retry toan bo dong loi
- export error list
- thong ke success/fail/running

### Luu y

Day la noi nhieu UI state nhat.
Khi sua file nay, can test:

- rebuild rows
- itemChanged trong table
- filter combo
- run/cancel
- retry actions

## 6.6 `gui/help_tab.py`

Tab huong dan cho user cuoi, khong phai cho dev.

Nen giu:

- ngan
- ro
- khong technical
- co cach lien he support

## 6.7 `gui/settings_dialog.py`

Noi luu:

- output dir
- downloads dir
- browser path
- chrome user data dir
- chrome profile dir
- show_browser_window
- batch interval
- max concurrent
- watch quiet seconds

## 7. Du lieu runtime

## 7.1 `data/settings.json`

Luu config app.

## 7.2 `data/accounts.json`

Luu ho so local.

## 7.3 `data/last_video_context.json`

Luu:

- `project_url`
- `detail_url`

Dung cho extend.

## 7.4 `data/projects/`

Luu du an local.

## 7.5 `output/images`

Anh tao ra.

## 7.6 `output/videos`

Video tao ra.

## 8. Startup flow

Khi mo app:

1. `main.py` goi `ensure_dirs()`
2. load settings
3. init auth
4. init browser assist + automation + generators
5. init batch / concat / project
6. tao `QApplication`
7. tao `MainWindow`
8. neu khong phai offscreen:
   - show popup `Vui long cho de kiem tra cap nhat...`
   - check update
   - xong moi cho user thao tac

## 9. Runtime flows chi tiet

## 9.1 Dang nhap Flow

1. User vao tab Tai khoan
2. Bam `Mo trinh duyet dang nhap Flow`
3. Browser cua app mo dung trang Flow
4. User dang nhap Google
5. App doc `Preferences`
6. Email/ten user tu dong hien o tab Tai khoan

## 9.2 Tao anh

1. User nhap prompt
2. Chon output count / quality / orientation
3. Co the chon anh tham chieu
4. Bam `Tao ngay bay gio👍`
5. `FlowGenerator` goi `FlowAutomation`
6. Flow render
7. App vao detail tung anh
8. Download tung file
9. Save ve `output/images`

## 9.3 Tao video text

1. User nhap prompt
2. Chon ratio / quality / so video
3. Bam generate
4. `VideoGenerator` goi `VideoAutomation`
5. Tao project
6. Submit prompt
7. Wait render
8. Tim tile
9. Mo link `/edit/...`
10. Download
11. Save ve `output/videos`
12. Luu `project_url` + `detail_url`

## 9.4 Tao video tu 1 anh

Giong text, nhung co `input[type=file]` nap 1 anh truoc khi submit.

## 9.5 Tao video tu anh dau/cuoi

1. Nap `start_image`
2. chon marker `End`
3. nap `end_image`
4. submit prompt

## 9.6 Tao video tu thanh phan

1. Nap anh dau tien
2. lap `Add Media`
3. nap them toi da 4 anh
4. submit prompt

## 9.7 Extend chain

1. Prompt 1 tao video goc
2. save context
3. Prompt 2 mo lai detail
4. click `Extend`
5. nhap prompt moi
6. cho render
7. download `Full Video`
8. cap nhat context
9. Prompt 3 lap lai

## 9.8 Batch

### Anh

- co the song song
- shared runtime `max_pages = max_concurrent`

### Video

- text/image/start_end/ingredients co the batch
- extend chain force sequential

## 10. Chien luoc on dinh / scale

Vi project dung UI automation thay vi API public, goc giam loi la:

1. Dung selector on dinh nhat co the
2. Giam phu thuoc click overlay
3. Uu tien link / structure thay vi icon text
4. Reuse runtime
5. Han che mo nhieu browser
6. Co retry generator
7. Co preset an toan
8. Co environment check
9. Co fallback 1080p cho cac case Flow hay loi

### Preset an toan

Anh:

- 1 anh
- 1080p
- ngang
- batch parallel 2

Video:

- 1 video
- 1080p
- 16:9
- 8s
- batch sequential 1

Muc tieu:

- user moi it fail
- giam ticket support
- scale len nhieu user an toan hon

## 11. Cach debug khi user bao loi

## 11.1 User bao khong tao duoc

Lam theo thu tu:

1. yeu cau user vao `Cong cu -> Kiem tra moi truong`
2. kiem tra user da dang nhap Flow chua
3. kiem tra email co hien trong tab Tai khoan khong
4. kiem tra machine co browser path / downloads dir hop le khong
5. thu lai voi preset an toan
6. thu lai voi 1080p va 1 output

## 11.2 Anh reference 2K/4K fail

Hien tai behavior dung la:

- app tu ha ve 1080p

Neu user bao “toi chon 4K ma file ra khong phai 4K”, day la fail-safe co chu y.

## 11.3 Video render xong ma khong tai

Check:

- tile selector co doi khong
- detail page co nut Download khong
- menu download co doi cau truc khong
- co menu 2 tang khong

Probe files huu ich:

- `data/video_post_render_probe.json`
- `data/extend_probe.json`
- `data/extend_download_ui_probe.json`

## 11.4 Extend fail

Check:

- `last_video_context.json` co `project_url` va `detail_url` khong
- detail page co nut `Extend` khong
- download menu la `Full Video` hay `Clip`

## 12. Build va release

## 12.1 Build Windows local

Script:

- [release_tools/build_windows.py]

Sinh ra:

- `build/dist/Tool Veo3's Thinh/`
- `release/Tool-Veo3s-Thinh-win.zip`

## 12.2 Build macOS

Script:

- [release_tools/build_macos.py]

Can:

- GitHub Actions macOS runner
hoac
- may Mac that

## 12.3 Auto update

Manifest:

- `latest.json`

Version:

- `version.json`

Flow:

1. app doc manifest
2. so sanh version
3. download zip release
4. spawn updater
5. restart app

## 12.4 GitHub Releases

Workflow:

- `.github/workflows/release.yml`

Tai lieu:

- `docs/GITHUB_RELEASES.md`
- `docs/GITHUB_DESKTOP_TUNG_CU_BAM.md`
- `docs/HUONG_DAN_PUBLIC_GITHUB_TU_DONG_CAP_NHAT.md`

## 13. Quy trinh hotfix cho nguoi khong code

Neu ban chi biet dung Codex:

1. mo folder project
2. moi ta loi ro rang
3. yeu cau:
   - sua loi
   - test lai
   - tang version
   - build lai zip Windows
4. commit / push / run release workflow

Tai lieu bo sung:

- `docs/CODEx_FIX_GUIDE.md`

## 14. Test matrix da chay

Da chay that trong dot nay:

- `python -m compileall core gui main.py bootstrap.py`
- doc email profile browser
- tao anh `4 output / 2K`
- tao anh `reference / 4K request` voi fallback an toan
- tao video text
- tao video text -> extend
- tao video text -> extend -> extend
- download menu extend `Full Video`
- startup offscreen smoke

### Mau output da sinh trong dot nay

Anh:

- `output/images/1-image_clean_luxury_studio_product_photo_of_a_transparent_20260314_093815.png`
- `output/images/4-image_clean_luxury_studio_product_photo_of_a_transparent_20260314_093815.png`
- `output/images/1-image_premium_editorial_lighting_with_glass_reflections__20260314_094208.png`

Video:

- `output/videos/1-video_cinematic_close-up_of_a_luxury_perfume_bottle_on_a_20260314_083502.mp4`
- `output/videos/1-video_cinematic_reveal_of_a_perfume_bottle_with_warm_ref_20260314_093122.mp4`
- `output/videos/1-video_continue_the_same_product_shot_with_a_smooth_camer_20260314_093406.mp4`
- `output/videos/1-video_finish_with_a_dramatic_close-up_and_elegant_golden_20260314_093554.mp4`

## 15. Known backlog

Danh sach nay nen theo doi tiep:

1. Multi-profile browser thật cho nhieu account song song.
   - Hien tai account local va browser profile chua la 1 he da profile hoan chinh.

2. Update system can an toan hon nua.
   - Nhat la voi frozen onedir khi app dang chay.

3. Batch live test video 2 job dai hoi ton nhieu thoi gian.
   - Nen co automated nightly smoke hoac manual checklist ro rang.

4. Selector hardening tiep.
   - Nhieu cho trong Flow van dua tren text / icon material.

5. macOS real build + smoke.

## 16. Nguyen tac khi sua code

1. Dung test live sau moi sua lon.
2. Moi khi sua selector video, probe bang browser hien ro.
3. Kiem tra ca 2 luong:
   - render
   - download
4. Khong sua updater neu chua co ly do rat ro.
5. Neu Flow doi UI, uu tien:
   - href
   - structure
   - role
   hon la text icon

## 17. Checklist review cho dev moi

Dev moi vao project nen:

1. Doc file nay truoc
2. Doc:
   - `core/video_automation.py`
   - `core/flow_automation.py`
   - `core/flow_runtime.py`
   - `gui/video_tab.py`
   - `gui/flow_tab.py`
   - `core/updater.py`
3. Chay compileall
4. Mo app offscreen smoke
5. Dang nhap Flow tren may local
6. Test:
   - 1 anh
   - 1 video text
   - 1 extend
7. Xem docs release/update

## 18. Neu doi dev tiep quan muon viet lai mot phan

Phan nen can nhac viet lai dau tien neu co thoi gian:

1. `video_automation.py`
   - ly do: nhieu branch xu ly UI phuc tap nhat

2. `batch_widgets.py`
   - ly do: nhieu state UI + bang + retry/filter

3. `updater.py`
   - ly do: thao tac file khi frozen app la vung nhay cam

## 19. Ket luan cho doi tiep quan

Day khong phai la project “API client”.
Day la “browser automation desktop product” duoc lam theo huong:

- uu tien hop le
- uu tien user-friendly
- uu tien tinh on dinh trong thuc te

Neu muon tiep tuc phat trien on dinh, can xem 3 tru cot:

1. Flow selector resilience
2. Runtime/browser profile discipline
3. Release/update discipline

Neu giu duoc 3 truc nay, project co the tiep tuc scale va maintain.
