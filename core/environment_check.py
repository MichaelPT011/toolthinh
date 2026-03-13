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
            checks.append(self._ok("Browser", f"Tim thay browser: {browser_path}"))
        elif self.browser_assist.can_auto_install_browser():
            checks.append(
                self._warning(
                    "Browser",
                    "May chua co Chrome san. App co the tu tai browser chinh thuc khi can.",
                )
            )
        else:
            checks.append(self._error("Browser", "Khong tim thay browser va cung khong the tu tai."))

        downloads_dir = Path(self.settings.get("downloads_dir") or Path.home() / "Downloads").expanduser()
        checks.append(self._check_directory("Thu muc tai xuong", downloads_dir))

        output_dir = Path(self.settings.get("output_dir") or "").expanduser()
        checks.append(self._check_directory("Thu muc dau ra", output_dir))

        user_data_dir = Path(self.browser_assist._effective_user_data_dir()).expanduser()
        checks.append(self._check_directory("Thu muc du lieu browser", user_data_dir))

        profile_dir = str(self.settings.get("chrome_profile_dir") or "Default").strip() or "Default"
        checks.append(self._ok("Profile browser", f"Dang dung profile: {profile_dir}"))

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
            return self._ok(title, f"Co the ghi du lieu vao: {directory}")
        except Exception as exc:
            return self._error(title, f"Khong the ghi vao {directory}: {exc}")

    def _check_active_accounts(self) -> dict:
        if self.auth is None:
            return self._warning("Dang nhap Flow", "Khong kiem tra duoc trang thai dang nhap tu man hinh nay.")
        try:
            active = len(self.auth.get_active_accounts())
        except Exception:
            active = 0
        if active > 0:
            return self._ok("Dang nhap Flow", f"Dang co {active} ho so hoat dong.")
        return self._warning(
            "Dang nhap Flow",
            "Chua co ho so hoat dong. Hay mo tab Tai khoan va dang nhap Flow truoc khi tao.",
        )

    def _check_update_manifest(self) -> dict:
        return self._ok("Auto update", f"Da khoa nguon cap nhat chinh thuc: {OFFICIAL_UPDATE_MANIFEST_URL}")

    def _check_download_folder_health(self, downloads_dir: Path) -> list[dict]:
        checks: list[dict] = []
        stale_partial = sorted(downloads_dir.glob("*.crdownload"))
        if stale_partial:
            checks.append(
                self._warning(
                    "Tai xuong dang do",
                    f"Co {len(stale_partial)} file tai do trong Downloads. Nen xoa de tranh app nhan nham.",
                )
            )
        else:
            checks.append(self._ok("Tai xuong dang do", "Khong co file tai do gay nhieu."))

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
                    "Thu muc Downloads",
                    "Downloads dang co rat nhieu file media. Nen don bot de app theo doi nhanh va chinh xac hon.",
                )
            )
        else:
            checks.append(self._ok("Thu muc Downloads", "So luong file media trong Downloads dang o muc an toan."))
        return checks

    def _check_playwright(self) -> dict:
        try:
            importlib.import_module("playwright.async_api")
            return self._ok("Playwright", "Thu vien automation da san sang.")
        except Exception as exc:
            return self._error("Playwright", f"Thieu hoac loi Playwright: {exc}")

    async def _check_browser_launch(self, browser_path: str) -> dict:
        try:
            module = importlib.import_module("playwright.async_api")
            async_playwright = module.async_playwright
        except Exception as exc:
            return self._error("Mo browser thu nghiem", f"Khong the nap Playwright de test browser: {exc}")

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
            return self._ok("Mo browser thu nghiem", "Browser automation mo va dong thu thanh cong.")
        except Exception as exc:
            return self._error("Mo browser thu nghiem", f"Browser automation chua chay on: {exc}")

    def _render_report(self, checks: list[dict], ok_count: int, warning_count: int, error_count: int) -> str:
        lines = [
            "BAO CAO KIEM TRA MOI TRUONG",
            "",
            f"OK: {ok_count} | Canh bao: {warning_count} | Loi: {error_count}",
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
