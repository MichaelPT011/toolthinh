"""Automate Flow video creation using a shared hidden Chrome runtime."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path

from core.config import FLOW_HOME_URL
from core.flow_automation import FlowAutomation
from core.flow_runtime import FlowBrowserRuntime

logger = logging.getLogger(__name__)


class VideoAutomation(FlowAutomation):
    """Drive Flow video creation without showing a browser window on screen."""

    async def generate_videos(
        self,
        prompt: str,
        output_dir: Path,
        prefix: str,
        aspect_ratio: str = "16:9",
        duration: str = "8s",
        num_outputs: int = 1,
        download_quality: str = "1080p",
        mode: str = "text",
        image_path: str | None = None,
        start_image_path: str | None = None,
        end_image_path: str | None = None,
        ingredient_paths: list[str] | None = None,
        extend_video_path: str | None = None,
        runtime: FlowBrowserRuntime | None = None,
        cancel_event: asyncio.Event | None = None,
        progress_callback=None,
        status_callback=None,
    ) -> list[str]:
        del duration
        del extend_video_path
        PlaywrightError, PlaywrightTimeoutError, _async_playwright = self._load_playwright()

        try:
            if runtime is None:
                async with self.create_shared_runtime(1) as shared_runtime:
                    return await self._generate_videos_with_runtime(
                        shared_runtime,
                        prompt,
                        output_dir,
                        prefix,
                        aspect_ratio=aspect_ratio,
                        num_outputs=num_outputs,
                        download_quality=download_quality,
                        mode=mode,
                        image_path=image_path,
                        start_image_path=start_image_path,
                        end_image_path=end_image_path,
                        ingredient_paths=ingredient_paths,
                        cancel_event=cancel_event,
                        progress_callback=progress_callback,
                        status_callback=status_callback,
                    )
            return await self._generate_videos_with_runtime(
                runtime,
                prompt,
                output_dir,
                prefix,
                aspect_ratio=aspect_ratio,
                num_outputs=num_outputs,
                download_quality=download_quality,
                mode=mode,
                image_path=image_path,
                start_image_path=start_image_path,
                end_image_path=end_image_path,
                ingredient_paths=ingredient_paths,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )
        except asyncio.CancelledError:
            raise
        except PlaywrightTimeoutError as exc:
            raise RuntimeError("Flow video timed out while waiting for the result.") from exc
        except PlaywrightError as exc:
            message = str(exc)
            lowered = message.lower()
            if "user data directory is already in use" in lowered or "target page, context or browser has been closed" in lowered:
                raise RuntimeError(
                    "Chrome profile is already open. Close the Flow login browser window, then try Generate again."
                ) from exc
            raise RuntimeError(f"Flow video automation failed: {message}") from exc

    async def _generate_videos_with_runtime(
        self,
        runtime: FlowBrowserRuntime,
        prompt: str,
        output_dir: Path,
        prefix: str,
        *,
        aspect_ratio: str,
        num_outputs: int,
        download_quality: str,
        mode: str,
        image_path: str | None,
        start_image_path: str | None,
        end_image_path: str | None,
        ingredient_paths: list[str] | None,
        cancel_event: asyncio.Event | None,
        progress_callback,
        status_callback,
    ) -> list[str]:
        requested = max(1, min(int(num_outputs or 1), 4))
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []

        # Flow is much less stable with x2/x3/x4 video output buttons.
        # We keep the user-facing count, but produce it as repeated x1 runs.
        for output_index in range(requested):
            async with runtime.page() as page:
                self._ensure_not_cancelled(cancel_event)
                scoped_progress = self._scoped_progress_callback(progress_callback, output_index, requested)
                scoped_status = self._scoped_status_callback(status_callback, output_index, requested)

                scoped_status("Đang khởi động Flow video...")
                await page.goto(FLOW_HOME_URL, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(4000)
                await self._assert_flow_ready(page)

                scoped_progress(5)
                scoped_status("Đang tạo project video...")
                await self._open_new_project(page, cancel_event=cancel_event)
                await page.wait_for_timeout(6000)

                self._ensure_not_cancelled(cancel_event)
                await self._configure_video_options(page, 1, aspect_ratio, mode)
                await self._upload_media_for_mode(
                    page,
                    mode,
                    image_path=image_path,
                    start_image_path=start_image_path,
                    end_image_path=end_image_path,
                    ingredient_paths=ingredient_paths or [],
                )
                scoped_progress(12)
                scoped_status("Đã gửi yêu cầu tạo video lên Flow.")

                prompt_box = page.locator('[role="textbox"]').first
                await prompt_box.click(force=True)
                await page.keyboard.press("Control+A")
                await page.keyboard.type(prompt)
                await page.wait_for_timeout(1200)
                await page.get_by_role("button", name="Create").last.click(force=True)

                await self._wait_for_video_result(page, 1, cancel_event, scoped_progress, scoped_status)
                saved_paths.extend(
                    await self._download_videos(
                        runtime,
                        page,
                        output_dir,
                        prefix,
                        1,
                        download_quality,
                        cancel_event,
                        scoped_progress,
                        scoped_status,
                        start_index=output_index,
                    )
                )

        self._emit_progress(progress_callback, 100)
        self._emit_status(status_callback, f"Đã tải xong {len(saved_paths)}/{requested} video.")
        return saved_paths

    def _scoped_progress_callback(self, callback, output_index: int, requested: int):
        if not callback:
            return lambda _value: None

        segment_start = int((output_index / requested) * 100)
        segment_end = int(((output_index + 1) / requested) * 100)
        segment_span = max(1, segment_end - segment_start)

        def emit(value: int) -> None:
            normalized = max(0, min(100, int(value)))
            scaled = min(100, segment_start + int((normalized / 100) * segment_span))
            callback(scaled)

        return emit

    def _scoped_status_callback(self, callback, output_index: int, requested: int):
        if not callback:
            return lambda _text: None

        prefix = f"[{output_index + 1}/{requested}] "

        def emit(text: str) -> None:
            callback(f"{prefix}{text}")

        return emit

    async def _configure_video_options(self, page, requested: int, aspect_ratio: str, mode: str) -> None:
        tabs = await self._open_options_panel(page, minimum_tabs=8, error_message="Flow video options panel did not open correctly.")

        await tabs.filter(has_text="videocam").first.click(force=True)
        await page.wait_for_timeout(600)

        if mode == "ingredients":
            await tabs.filter(has_text="chrome_extension").first.click(force=True)
        else:
            await tabs.filter(has_text="crop_free").first.click(force=True)

        orientation_label = "crop_16_9" if aspect_ratio == "16:9" else "crop_9_16"
        await tabs.filter(has_text=orientation_label).first.click(force=True)
        await tabs.filter(has_text=f"x{requested}").first.click(force=True)
        await page.wait_for_timeout(500)

        model_dropdown = page.locator("button").filter(has_text="arrow_drop_down").last
        await model_dropdown.click(force=True)
        await page.wait_for_timeout(500)
        await page.locator('[role="menuitem"]').filter(has_text="Veo 3.1 - Fast").first.click(force=True)
        await page.wait_for_timeout(500)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

    async def _upload_media_for_mode(
        self,
        page,
        mode: str,
        *,
        image_path: str | None,
        start_image_path: str | None,
        end_image_path: str | None,
        ingredient_paths: list[str],
    ) -> None:
        if mode == "extend":
            raise RuntimeError("Flow chưa lộ rõ luồng kéo dài video tự động ổn định trên editor hiện tại.")

        file_input = page.locator('input[type="file"]').first
        if await file_input.count() == 0:
            return

        if mode == "image" and image_path:
            await file_input.set_input_files(image_path)
            await page.wait_for_timeout(6000)
            return

        if mode == "start_end" and start_image_path:
            await file_input.set_input_files(start_image_path)
            await page.wait_for_timeout(6000)
            if end_image_path:
                end_marker = page.get_by_text("End")
                if await end_marker.count():
                    await end_marker.first.click(force=True)
                    await page.wait_for_timeout(800)
                    await file_input.set_input_files(end_image_path)
                    await page.wait_for_timeout(6000)
            return

        if mode == "ingredients" and ingredient_paths:
            await file_input.set_input_files(ingredient_paths[0])
            await page.wait_for_timeout(5000)
            for extra_path in ingredient_paths[1:4]:
                add_button = page.get_by_role("button", name="Add Media")
                if await add_button.count():
                    await add_button.first.click(force=True)
                    await page.wait_for_timeout(800)
                await file_input.set_input_files(extra_path)
                await page.wait_for_timeout(5000)

    def _format_failure(self, body: str) -> str:
        match = re.search(r"(\d+)%", body)
        if match:
            return f"Flow đã submit video nhưng server trả Failed ở khoảng {match.group(1)}%."
        return "Flow đã submit video nhưng server trả Failed."

    async def _download_videos(
        self,
        runtime: FlowBrowserRuntime,
        page,
        output_dir: Path,
        prefix: str,
        requested: int,
        download_quality: str,
        cancel_event: asyncio.Event | None,
        progress_callback=None,
        status_callback=None,
        start_index: int = 0,
    ) -> list[str]:
        saved_paths: list[str] = []
        target_quality = self._video_quality_label(download_quality)

        video_count = await page.locator("video").count()
        if video_count == 0:
            raise RuntimeError("Flow không hiển thị video nào để tải về.")

        total = min(requested, video_count)
        for index in range(total):
            self._ensure_not_cancelled(cancel_event)
            self._emit_status(status_callback, f"Đang mở video {index + 1}/{total}...")
            play_button = page.get_by_role("button").filter(has_text="play_circle").nth(index)
            await play_button.click(force=True)
            await page.wait_for_timeout(2500)

            output_path = output_dir / f"{start_index + index + 1}-{prefix}.mp4"
            quality_text = str(download_quality or "1080p").upper()
            async with runtime.download_slot():
                if quality_text in {"2K", "4K"}:
                    self._emit_status(status_callback, f"Đang yêu cầu bản upscale {quality_text} cho video {index + 1}/{total}...")
                else:
                    self._emit_status(status_callback, f"Đang tải video {index + 1}/{total}...")

                download_button = page.get_by_role("button", name="Download").first
                await download_button.click(force=True)
                await page.wait_for_timeout(500)
                menu_items = page.locator('[role="menuitem"]')
                if await menu_items.count():
                    async with page.expect_download(timeout=180000) as download_info:
                        preferred = menu_items.filter(has_text=target_quality)
                        if await preferred.count():
                            await preferred.first.click(force=True)
                        else:
                            fallback = await self._pick_video_download_item(menu_items)
                            await fallback.click(force=True)
                    download = await download_info.value
                else:
                    async with page.expect_download(timeout=180000) as download_info:
                        await download_button.click(force=True)
                    download = await download_info.value

                await download.save_as(str(output_path))

            saved_paths.append(str(output_path))
            logger.info("Saved Flow video: %s", output_path)
            self._emit_progress(progress_callback, int(((index + 1) / max(1, total)) * 100))
            self._emit_status(status_callback, f"Đã tải xong video {index + 1}/{total}.")

            back_button = page.get_by_role("button", name="Back")
            if await back_button.count():
                await back_button.first.click(force=True)
                await page.wait_for_timeout(1200)

        return saved_paths

    async def _wait_for_video_result(
        self,
        page,
        requested: int,
        cancel_event: asyncio.Event | None,
        progress_callback=None,
        status_callback=None,
    ) -> None:
        stable_failed_seconds = 0
        max_failed_grace_seconds = 180
        last_reported_progress = -1
        last_video_count = 0

        for _ in range(180):
            self._ensure_not_cancelled(cancel_event)
            await page.wait_for_timeout(5000)
            body = await page.locator("body").inner_text()
            video_count = await page.locator("video").count()
            last_video_count = video_count
            progress = self._extract_progress(body)

            if progress is not None and last_reported_progress < 0 and progress > 50:
                progress = None

            if progress is not None and progress >= last_reported_progress and progress != last_reported_progress:
                last_reported_progress = progress
                self._emit_progress(progress_callback, progress)
                self._emit_status(status_callback, f"Flow đang render video: {progress}%")
            elif progress is None:
                self._emit_status(status_callback, "Flow đang xếp hàng hoặc render video...")

            if video_count:
                if video_count >= requested:
                    self._emit_progress(progress_callback, 95)
                    self._emit_status(status_callback, f"Flow đã render đủ {requested}/{requested} video. Chuẩn bị tải...")
                    return
                self._emit_progress(progress_callback, min(92, 80 + int((video_count / max(1, requested)) * 12)))
                self._emit_status(
                    status_callback,
                    f"Flow đã render {video_count}/{requested} video. App đang chờ đủ số lượng...",
                )

            has_failed = "Failed" in body or "Something went wrong." in body
            if has_failed:
                stable_failed_seconds += 5
                if stable_failed_seconds >= max_failed_grace_seconds:
                    raise RuntimeError(self._format_failure(body))
                self._emit_status(
                    status_callback,
                    "Flow đang báo trạng thái chưa ổn định. App tiếp tục chờ thêm để tránh fail sớm...",
                )
            else:
                stable_failed_seconds = 0

        if last_video_count:
            raise RuntimeError(f"Flow chỉ render được {last_video_count}/{requested} video.")
        raise RuntimeError("Flow video did not return a downloadable result.")

    def _extract_progress(self, body: str) -> int | None:
        matches = re.findall(r"(\d+)\s*%", body)
        if not matches:
            return None
        try:
            return max(0, min(100, int(matches[-1])))
        except ValueError:
            return None

    def _video_quality_label(self, quality: str) -> str:
        normalized = str(quality or "1080p").strip().lower()
        if normalized in {"1080", "1080p", "1k"}:
            return "1080p"
        if normalized == "2k":
            return "2K"
        if normalized == "4k":
            return "4K"
        return "1080p"

    async def _pick_video_download_item(self, menu_items):
        priorities = ["1080p", "720p", "4K", "270p"]
        for target in priorities:
            candidate = menu_items.filter(has_text=target)
            if await candidate.count():
                return candidate.first
        return menu_items.first
