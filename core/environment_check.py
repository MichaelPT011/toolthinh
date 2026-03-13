"""Environment diagnostics for safer first-run and scale-out support."""

from __future__ import annotations

import importlib
import tempfile
from pathlib import Path

from core.config import OFFICIAL_UPDATE_MANIFEST_URL


class EnvironmentChecker:
    """Run local diagnostics and return a user-facing report."""

    def __init__(self, settings: dict, browser_assist, auth=None) -> None:
        self.settings = dict(settings)
        self.browser_assist = browser_assist
        self.auth = auth

    async def run(self) -> dict:
        checks: list[dict] = []

        browser_path = self.browser_assist._resolve_browser_path()
        if browser_path:
            checks.append(self._ok("Browser", f"Tìm thấy browser: {browser_path}"))
        else:
            checks.append(self._error("Browser", "Không tìm thấy browser. App sẽ không thể chạy automation."))

        downloads_dir = Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()
        checks.append(self._check_directory("Thư mục tải xuống", downloads_dir))

        output_dir = Path(self.settings.get("output_dir") or "").expanduser()
        checks.append(self._check_directory("Thư mục đầu ra", output_dir))

        user_data_dir = Path(self.browser_assist._effective_user_data_dir()).expanduser()
        checks.append(self._check_directory("Thư mục dữ liệu browser", user_data_dir))

        profile_dir = str(self.settings.get("chrome_profile_dir") or "Default").strip() or "Default"
        checks.append(self._ok("Profile browser", f"Đang dùng profile: {profile_dir}"))

        checks.append(self._check_active_accounts())
        checks.append(self._check_update_manifest())
        checks.extend(self._check_download_folder_health(downloads_dir))
        checks.append(self._check_playwright())

        if browser_path:
            checks.append(await self._check_browser_launch(browser_path))

        ok_count = sum(1 for item in checks if item["status"] == "ok")
        warning_count = sum(1 for item in checks if item["status"] == "warning")
        error_count = sum(1 for item in checks if item["status"] == "error")
        overall = "ok"
        if error_count:
            overall = "error"
        elif warning_count:
            overall = "warning"

        return {
            "overall": overall,
            "ok_count": ok_count,
            "warning_count": warning_count,
            "error_count": error_count,
            "checks": checks,
            "report": self._render_report(checks, ok_count, warning_count, error_count),
        }

    def _check_directory(self, title: str, directory: Path) -> dict:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return self._ok(title, f"Sẵn sàng ghi dữ liệu: {directory}")
        except Exception as exc:
            return self._error(title, f"Không thể ghi vào {directory}: {exc}")

    def _check_active_accounts(self) -> dict:
        if self.auth is None:
            return self._warning("Đăng nhập Flow", "Không kiểm tra được trạng thái đăng nhập từ màn hình này.")
        try:
            active = len(self.auth.get_active_accounts())
        except Exception:
            active = 0
        if active > 0:
            return self._ok("Đăng nhập Flow", f"Đang có {active} hồ sơ hoạt động.")
        return self._warning(
            "Đăng nhập Flow",
            "Chưa có hồ sơ hoạt động. Hãy mở tab Tài khoản và đăng nhập Flow trước khi tạo.",
        )

    def _check_update_manifest(self) -> dict:
        return self._ok("Auto update", f"Đã khóa nguồn cập nhật chính thức: {OFFICIAL_UPDATE_MANIFEST_URL}")

    def _check_download_folder_health(self, downloads_dir: Path) -> list[dict]:
        checks: list[dict] = []
        stale_partial = sorted(downloads_dir.glob("*.crdownload"))
        if stale_partial:
            checks.append(
                self._warning(
                    "Tải xuống dang dở",
                    f"Có {len(stale_partial)} file tải dở trong thư mục Downloads. Nên xóa để tránh app nhận nhầm.",
                )
            )
        else:
            checks.append(self._ok("Tải xuống dang dở", "Không có file tải dở gây nhiễu."))

        very_large_count = 0
        try:
            for path in downloads_dir.iterdir():
                if path.is_file() and path.suffix.lower() in {".mp4", ".mov", ".png", ".jpg", ".jpeg", ".webp"}:
                    very_large_count += 1
        except OSError:
            very_large_count = 0

        if very_large_count > 300:
            checks.append(
                self._warning(
                    "Thư mục Downloads",
                    "Downloads đang có rất nhiều file media. Nên dọn bớt để app theo dõi nhanh và chính xác hơn.",
                )
            )
        else:
            checks.append(self._ok("Thư mục Downloads", "Số lượng file media trong Downloads đang ở mức an toàn."))
        return checks

    def _check_playwright(self) -> dict:
        try:
            importlib.import_module("playwright.async_api")
            return self._ok("Playwright", "Thư viện automation đã sẵn sàng.")
        except Exception as exc:
            return self._error("Playwright", f"Thiếu hoặc lỗi Playwright: {exc}")

    async def _check_browser_launch(self, browser_path: str) -> dict:
        try:
            module = importlib.import_module("playwright.async_api")
            async_playwright = module.async_playwright
        except Exception as exc:
            return self._error("Mở browser thử nghiệm", f"Không thể nạp Playwright để test browser: {exc}")

        try:
            with tempfile.TemporaryDirectory(prefix="veo3_env_check_") as temp_dir:
                async with async_playwright() as playwright:
                    context = await playwright.chromium.launch_persistent_context(
                        temp_dir,
                        executable_path=browser_path,
                        headless=True,
                        args=[
                            "--mute-audio",
                            "--no-first-run",
                            "--no-default-browser-check",
                            "--disable-session-crashed-bubble",
                        ],
                        viewport={"width": 1200, "height": 900},
                        accept_downloads=True,
                    )
                    try:
                        page = context.pages[0] if context.pages else await context.new_page()
                        await page.goto("https://example.com", wait_until="domcontentloaded", timeout=60000)
                    finally:
                        await context.close()
            return self._ok("Mở browser thử nghiệm", "Browser automation mở và đóng thử thành công.")
        except Exception as exc:
            return self._error("Mở browser thử nghiệm", f"Browser automation chưa chạy ổn: {exc}")

    def _render_report(self, checks: list[dict], ok_count: int, warning_count: int, error_count: int) -> str:
        lines = [
            "BÁO CÁO KIỂM TRA MÔI TRƯỜNG",
            "",
            f"OK: {ok_count} | Cảnh báo: {warning_count} | Lỗi: {error_count}",
            "",
        ]
        icons = {"ok": "OK", "warning": "CANH BAO", "error": "LOI"}
        for item in checks:
            lines.append(f"[{icons[item['status']]}] {item['title']}")
            lines.append(f"  - {item['detail']}")
        return "\n".join(lines)

    def _ok(self, title: str, detail: str) -> dict:
        return {"status": "ok", "title": title, "detail": detail}

    def _warning(self, title: str, detail: str) -> dict:
        return {"status": "warning", "title": title, "detail": detail}

    def _error(self, title: str, detail: str) -> dict:
        return {"status": "error", "title": title, "detail": detail}
