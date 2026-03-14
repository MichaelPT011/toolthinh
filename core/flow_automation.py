"""Automate image creation in Flow using a shared hidden Chrome runtime."""

from __future__ import annotations

import asyncio
import importlib
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

from core.config import FLOW_HOME_URL
from core.flow_runtime import FlowBrowserRuntime

logger = logging.getLogger(__name__)


class FlowAutomation:
    """Drive the official Flow UI with Playwright and save downloaded images."""

    def __init__(self, browser_assist) -> None:
        self.browser_assist = browser_assist

    def create_shared_runtime(self, max_pages: int = 1) -> FlowBrowserRuntime:
        return FlowBrowserRuntime(self.browser_assist, self._load_playwright, max_pages=max_pages)

    async def generate_images(
        self,
        prompt: str,
        output_dir: Path,
        prefix: str,
        num_images: int = 1,
        download_quality: str = "1080p",
        orientation: str = "landscape",
        image_path: str | None = None,
        runtime: FlowBrowserRuntime | None = None,
        cancel_event: asyncio.Event | None = None,
        progress_callback=None,
        status_callback=None,
    ) -> list[str]:
        PlaywrightError, PlaywrightTimeoutError, _async_playwright = self._load_playwright()

        try:
            if runtime is None:
                async with self.create_shared_runtime(1) as shared_runtime:
                    return await self._generate_images_with_runtime(
                        shared_runtime,
                        prompt,
                        output_dir,
                        prefix,
                        num_images=num_images,
                        download_quality=download_quality,
                        orientation=orientation,
                        image_path=image_path,
                        cancel_event=cancel_event,
                        progress_callback=progress_callback,
                        status_callback=status_callback,
                    )
            return await self._generate_images_with_runtime(
                runtime,
                prompt,
                output_dir,
                prefix,
                num_images=num_images,
                download_quality=download_quality,
                orientation=orientation,
                image_path=image_path,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )
        except asyncio.CancelledError:
            raise
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Flow automation timed out while waiting for the generated image.") from exc
        except PlaywrightError as exc:
            message = str(exc)
            lowered = message.lower()
            if "user data directory is already in use" in lowered or "target page, context or browser has been closed" in lowered:
                raise RuntimeError(
                    "Chrome profile is already open. Close the Flow login browser window, then try Generate again."
                ) from exc
            raise RuntimeError(f"Flow automation failed: {message}") from exc

    async def _generate_images_with_runtime(
        self,
        runtime: FlowBrowserRuntime,
        prompt: str,
        output_dir: Path,
        prefix: str,
        *,
        num_images: int,
        download_quality: str,
        orientation: str,
        image_path: str | None,
        cancel_event: asyncio.Event | None,
        progress_callback,
        status_callback,
    ) -> list[str]:
        requested = max(1, min(int(num_images or 1), 4))
        quality_label = self._download_quality_label(download_quality)
        quality_text = str(download_quality or "1080p").upper()
        if image_path and quality_label != "1K":
            self._emit_status(
                status_callback,
                "Flow hiện thường chỉ cho tải 1080p với ảnh tham chiếu. App sẽ tự hạ về 1080p để tránh lỗi 2K/4K.",
            )
            quality_label = "1K"
            quality_text = "1080P"

        async with runtime.page() as page:
            self._ensure_not_cancelled(cancel_event)
            self._emit_status(status_callback, "Đang mở Flow ảnh...")
            await page.goto(FLOW_HOME_URL, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(4000)
            await self._assert_flow_ready(page)

            self._emit_progress(progress_callback, 5)
            self._emit_status(status_callback, "Đang tạo project ảnh...")
            await self._open_new_project(page, cancel_event=cancel_event)
            await page.wait_for_timeout(5000)

            self._ensure_not_cancelled(cancel_event)
            await self._configure_image_options(page, requested, orientation)
            await self._upload_reference_image(page, image_path)
            self._emit_progress(progress_callback, 12)
            self._emit_status(status_callback, "Đã cấu hình ảnh. Đang gửi yêu cầu lên Flow...")

            prompt_box = page.locator('[role="textbox"]').first
            await prompt_box.click()
            await page.keyboard.press("Control+A")
            await page.keyboard.type(prompt)
            await page.wait_for_timeout(1200)
            await page.get_by_role("button", name="Create").last.click()

            await self._wait_for_generated_images(
                page,
                requested,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )

            output_dir.mkdir(parents=True, exist_ok=True)
            saved_paths: list[str] = []
            for index in range(requested):
                self._ensure_not_cancelled(cancel_event)
                if index:
                    back_button = page.get_by_role("button", name="Back")
                    if await back_button.count():
                        await back_button.first.click()
                        await page.wait_for_timeout(1200)

                self._emit_status(status_callback, f"Đang mở ảnh {index + 1}/{requested}...")
                await page.locator('img[alt="Generated image"]').nth(index).click()
                await page.wait_for_timeout(2200)

                saved_path = await self._download_image_variant(
                    runtime,
                    page,
                    output_dir,
                    prefix,
                    index,
                    quality_label,
                    quality_text,
                    cancel_event,
                    status_callback,
                )
                saved_paths.append(saved_path)
                logger.info("Saved Flow image: %s", saved_path)
                self._emit_progress(progress_callback, int(((index + 1) / max(1, requested)) * 100))

            self._emit_status(status_callback, f"Đã tải xong {len(saved_paths)} ảnh.")
            return saved_paths

    def _load_playwright(self):
        try:
            return self._import_playwright()
        except ImportError:
            self._install_playwright()
            try:
                return self._import_playwright()
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright could not be installed automatically. Run the app with "
                    f"'{sys.executable}' or install 'playwright' for this Python interpreter."
                ) from exc

    def _import_playwright(self):
        module = importlib.import_module("playwright.async_api")
        return module.Error, module.TimeoutError, module.async_playwright

    def _install_playwright(self) -> None:
        logger.info("Playwright is missing in %s. Installing it now.", sys.executable)
        command = [sys.executable, "-m", "pip", "install", "playwright>=1.58.0"]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Playwright installation completed.")
            return

        fallback = [sys.executable, "-m", "pip", "install", "--user", "playwright>=1.58.0"]
        result = subprocess.run(fallback, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("Playwright installation completed with --user.")
            return

        logger.error("Playwright install failed. stdout=%s stderr=%s", result.stdout, result.stderr)
        raise RuntimeError(
            "Playwright is not installed for this Python interpreter and automatic install failed."
        )

    async def _assert_flow_ready(self, page) -> None:
        body = await page.locator("body").inner_text()
        if "ISN'T AVAILABLE IN YOUR COUNTRY YET" in body:
            raise RuntimeError("Flow is not available for this browser session right now.")
        await page.get_by_role("button", name="New project").wait_for(timeout=120000)

    async def _open_new_project(self, page, *, cancel_event: asyncio.Event | None) -> None:
        if "/project/" in page.url:
            return

        button = page.get_by_role("button", name="New project")
        for _ in range(4):
            self._ensure_not_cancelled(cancel_event)
            await button.first.wait_for(timeout=30000)
            await button.first.click(force=True)
            for _ in range(24):
                self._ensure_not_cancelled(cancel_event)
                await page.wait_for_timeout(2500)
                if "/project/" in page.url:
                    return
                if await self._project_editor_ready(page):
                    return

        body = await page.locator("body").inner_text()
        raise RuntimeError(
            "Flow không chuyển sang màn project sau khi bấm New project. "
            f"Nội dung hiện tại: {body[:200]}"
        )

    async def _project_editor_ready(self, page) -> bool:
        prompt_box = page.locator('[role="textbox"]').first
        create_button = page.get_by_role("button", name="Create").last
        try:
            return await prompt_box.count() > 0 and await create_button.count() > 0
        except Exception:
            return False

    async def _configure_image_options(self, page, num_images: int, orientation: str) -> None:
        tabs = await self._open_options_panel(page, minimum_tabs=8, error_message="Flow options panel did not open correctly.")

        await tabs.nth(0).click(force=True)
        await tabs.nth(2 if orientation == "landscape" else 3).click(force=True)
        await tabs.nth(4 + (num_images - 1)).click(force=True)
        await page.wait_for_timeout(500)

        model_dropdown = page.locator("button").filter(has_text="arrow_drop_down").last
        await model_dropdown.click(force=True)
        await page.wait_for_timeout(500)
        await page.locator('[role="menuitem"]').filter(has_text="Nano Banana 2").first.click(force=True)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

    async def _open_options_panel(self, page, minimum_tabs: int, error_message: str):
        option_button = page.locator("button").filter(has_text="crop_").first
        tabs = page.get_by_role("tab")
        for _ in range(4):
            await option_button.click(force=True)
            await page.wait_for_timeout(1500)
            if await tabs.count() >= minimum_tabs:
                return tabs
        raise RuntimeError(error_message)

    async def _wait_for_generated_images(
        self,
        page,
        requested: int,
        *,
        cancel_event: asyncio.Event | None,
        progress_callback,
        status_callback,
    ) -> int:
        last_count = 0
        for _ in range(60):
            self._ensure_not_cancelled(cancel_event)
            await page.wait_for_timeout(5000)
            count = await page.locator('img[alt="Generated image"]').count()
            if count:
                estimate = 15 + int((count / max(1, requested)) * 65)
                self._emit_progress(progress_callback, max(15, min(80, estimate)))
                self._emit_status(status_callback, f"Flow đang render ảnh: {count}/{requested}")
            else:
                self._emit_status(status_callback, "Flow đang render ảnh...")
            if count >= requested:
                return count
            last_count = count

        if last_count:
            raise RuntimeError(f"Flow chỉ trả về {last_count}/{requested} ảnh.")
        raise RuntimeError("Flow did not return any generated images.")

    async def _download_image_variant(
        self,
        runtime: FlowBrowserRuntime,
        page,
        output_dir: Path,
        prefix: str,
        index: int,
        quality_label: str,
        quality_text: str,
        cancel_event: asyncio.Event | None,
        status_callback,
    ) -> str:
        extensions = {".png", ".jpg", ".jpeg", ".webp"}
        async with runtime.download_slot():
            self._ensure_not_cancelled(cancel_event)
            output_path = self._reserve_output_path(output_dir / f"{index + 1}-{prefix}.png")
            download_baseline = self.browser_assist.current_download_snapshot(extensions)
            download_button = page.get_by_role("button", name="Download")
            menu_items = page.locator('[role="menuitem"]')

            await download_button.click()
            await page.wait_for_timeout(400)
            requested_item = menu_items.filter(has_text=quality_label).first
            available_requested = await requested_item.count() > 0
            if not available_requested and quality_label != "1K":
                self._emit_status(
                    status_callback,
                    f"Flow hiện không có tùy chọn {quality_text} cho ảnh {index + 1}. App sẽ tự tải 1080p để tránh lỗi.",
                )
                quality_label = "1K"
                quality_text = "1080P"
                requested_item = menu_items.filter(has_text=quality_label).first
            if quality_label == "1K":
                self._emit_status(status_callback, f"Đang tải ảnh {index + 1} ({quality_text})...")
                try:
                    async with page.expect_download(timeout=180000) as download_info:
                        await requested_item.click(force=True)
                    download = await download_info.value
                    await download.save_as(str(output_path))
                    return str(output_path)
                except Exception:
                    external_file = await self._wait_for_external_download(
                        extensions,
                        download_baseline,
                        timeout_seconds=45,
                    )
                    if external_file:
                        shutil.copy2(external_file, output_path)
                        return str(output_path)
                    raise

            self._emit_status(status_callback, f"Đang upscale ảnh {index + 1} lên {quality_text}...")
            download = None
            try:
                async with page.expect_download(timeout=90000) as download_info:
                    await requested_item.click(force=True)
                download = await download_info.value
            except Exception:
                download = None

            if download is not None:
                await download.save_as(str(output_path))
                self._emit_status(status_callback, f"Đã upscale xong ảnh {index + 1} lên {quality_text}.")
                return str(output_path)

            external_file = await self._wait_for_external_download(
                extensions,
                download_baseline,
                timeout_seconds=20,
            )
            if external_file:
                shutil.copy2(external_file, output_path)
                self._emit_status(status_callback, f"Da tai xong anh {index + 1} ({quality_text}) qua theo doi file.")
                return str(output_path)

            deadline = time.monotonic() + (900 if quality_label == "4K" else 420)
            while time.monotonic() < deadline:
                self._ensure_not_cancelled(cancel_event)
                self._emit_status(status_callback, f"Đang chờ Flow hoàn tất upscale ảnh {index + 1} lên {quality_text}...")
                await page.wait_for_timeout(12000)
                external_file = await self._wait_for_external_download(
                    extensions,
                    download_baseline,
                    timeout_seconds=8,
                )
                if external_file:
                    shutil.copy2(external_file, output_path)
                    self._emit_status(status_callback, f"Da tai xong anh {index + 1} ({quality_text}) qua theo doi file.")
                    return str(output_path)
                try:
                    async with page.expect_download(timeout=25000) as download_info:
                        await download_button.click()
                        await page.wait_for_timeout(400)
                        await requested_item.click(force=True)
                    download = await download_info.value
                except Exception:
                    download = None
                if download is not None:
                    await download.save_as(str(output_path))
                    self._emit_status(status_callback, f"Đã upscale xong ảnh {index + 1} lên {quality_text}.")
                    return str(output_path)

            raise RuntimeError(f"Flow chưa hoàn tất upscale ảnh {quality_text}.")

    async def _upload_reference_image(self, page, image_path: str | None) -> None:
        if not image_path:
            return
        file_input = page.locator('input[type="file"]').first
        if await file_input.count() == 0:
            return
        await file_input.set_input_files(image_path)
        await page.wait_for_timeout(4000)

    def _download_quality_label(self, quality: str) -> str:
        normalized = str(quality or "1080p").strip().lower()
        if normalized in {"1080", "1080p", "1k"}:
            return "1K"
        if normalized == "2k":
            return "2K"
        if normalized == "4k":
            return "4K"
        return "1K"

    def _ensure_not_cancelled(self, cancel_event: asyncio.Event | None) -> None:
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()

    def _emit_progress(self, callback, value: int) -> None:
        if callback:
            callback(value)

    def _emit_status(self, callback, text: str) -> None:
        if callback:
            callback(text)

    def _reserve_output_path(self, path: Path) -> Path:
        candidate = path
        counter = 1
        while candidate.exists():
            candidate = path.with_name(f"{path.stem}_{counter}{path.suffix}")
            counter += 1
        return candidate

    async def _wait_for_external_download(
        self,
        extensions: set[str],
        baseline: set[Path],
        *,
        timeout_seconds: int,
    ) -> Path | None:
        downloads = await self.browser_assist.wait_for_downloads(
            extensions,
            timeout_seconds,
            expected_count=1,
            baseline=baseline,
        )
        if not downloads:
            return None
        return downloads[0]

    async def _wait_for_upscale_complete(
        self,
        page,
        quality_text: str,
        *,
        timeout_seconds: int,
        cancel_event: asyncio.Event | None,
        status_callback,
    ) -> None:
        for _ in range(max(1, timeout_seconds // 5)):
            self._ensure_not_cancelled(cancel_event)
            await page.wait_for_timeout(5000)
            body = await page.locator("body").inner_text()
            if "Upscaling complete" in body:
                return
            if "Upscaling your image" in body:
                self._emit_status(status_callback, f"Đang upscale ảnh lên {quality_text}...")
        raise RuntimeError(f"Flow chưa hoàn tất upscale ảnh {quality_text}.")
