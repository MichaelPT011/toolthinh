"""Automate Flow video creation using a shared Chrome runtime."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin

from core.config import FLOW_HOME_URL, LAST_VIDEO_CONTEXT_FILE
from core.flow_automation import FlowAutomation
from core.flow_runtime import FlowBrowserRuntime

logger = logging.getLogger(__name__)


class VideoAutomation(FlowAutomation):
    """Drive Flow video creation with resilient selectors and shared runtime."""

    def __init__(self, browser_assist) -> None:
        super().__init__(browser_assist)
        self._last_video_project_url, self._last_video_detail_url = self._load_last_video_context()

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
                        extend_video_path=extend_video_path,
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
                extend_video_path=extend_video_path,
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
        extend_video_path: str | None,
        cancel_event: asyncio.Event | None,
        progress_callback,
        status_callback,
    ) -> list[str]:
        requested = max(1, min(int(num_outputs or 1), 4))
        output_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[str] = []

        if mode == "extend":
            return await self._extend_videos_with_runtime(
                runtime,
                prompt,
                output_dir,
                prefix,
                requested=requested,
                download_quality=download_quality,
                extend_video_path=extend_video_path,
                cancel_event=cancel_event,
                progress_callback=progress_callback,
                status_callback=status_callback,
            )

        # Flow is unstable with x2/x3/x4 video output buttons. Produce the requested
        # count as repeated x1 runs while keeping the user-facing output count.
        for output_index in range(requested):
            async with runtime.page() as page:
                self._ensure_not_cancelled(cancel_event)
                scoped_progress = self._scoped_progress_callback(progress_callback, output_index, requested)
                scoped_status = self._scoped_status_callback(status_callback, output_index, requested)

                scoped_status("Dang khoi dong Flow video...")
                await page.goto(FLOW_HOME_URL, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(4000)
                await self._assert_flow_ready(page)

                scoped_progress(5)
                scoped_status("Dang tao project video...")
                await self._open_new_project(page, cancel_event=cancel_event)
                await page.wait_for_timeout(6000)
                self._remember_video_context(project_url=page.url)

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
                scoped_status("Da gui yeu cau tao video len Flow.")

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
        self._emit_status(status_callback, f"Da tai xong {len(saved_paths)}/{requested} video.")
        return saved_paths

    async def _extend_videos_with_runtime(
        self,
        runtime: FlowBrowserRuntime,
        prompt: str,
        output_dir: Path,
        prefix: str,
        *,
        requested: int,
        download_quality: str,
        extend_video_path: str | None,
        cancel_event: asyncio.Event | None,
        progress_callback,
        status_callback,
    ) -> list[str]:
        del extend_video_path

        if not self._last_video_project_url and not self._last_video_detail_url:
            raise RuntimeError(
                "Chua co project video gan nhat de keo dai. Hay tao it nhat 1 video thanh cong trong app truoc."
            )

        saved_paths: list[str] = []
        for output_index in range(requested):
            async with runtime.page() as page:
                self._ensure_not_cancelled(cancel_event)
                scoped_progress = self._scoped_progress_callback(progress_callback, output_index, requested)
                scoped_status = self._scoped_status_callback(status_callback, output_index, requested)

                detail_url = (self._last_video_detail_url or "").strip()
                project_url = (self._last_video_project_url or "").strip()
                if detail_url:
                    scoped_status("Dang mo clip gan nhat de keo dai...")
                    await page.goto(detail_url, wait_until="domcontentloaded", timeout=120000)
                    await page.wait_for_timeout(3500)
                elif project_url:
                    scoped_status("Dang mo project video gan nhat de keo dai...")
                    await page.goto(project_url, wait_until="domcontentloaded", timeout=120000)
                    await page.wait_for_timeout(5000)

                await self._open_latest_video_for_extend(page, cancel_event, scoped_status)

                scoped_progress(8)
                scoped_status("Dang chuyen sang che do Keo dai video...")
                extend_button = page.get_by_role("button").filter(has_text="Extend").first
                await extend_button.click(force=True)
                await page.wait_for_timeout(1000)

                prompt_box = page.locator('[role="textbox"]').first
                await prompt_box.click(force=True)
                await page.keyboard.press("Control+A")
                await page.keyboard.type(prompt)
                await page.wait_for_timeout(1000)
                await page.get_by_role("button", name="Create").last.click(force=True)

                await self._wait_for_extend_result(page, cancel_event, scoped_progress, scoped_status)
                self._remember_video_context(project_url=self._project_root_url(page.url), detail_url=page.url)

                output_path = output_dir / f"{output_index + 1}-{prefix}.mp4"
                saved_paths.append(
                    await self._download_current_video_detail(
                        runtime,
                        page,
                        output_path,
                        download_quality,
                        cancel_event,
                        scoped_progress,
                        scoped_status,
                    )
                )

        self._emit_progress(progress_callback, 100)
        self._emit_status(status_callback, f"Da tai xong {len(saved_paths)}/{requested} video keo dai.")
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
        tabs = await self._open_options_panel(
            page,
            minimum_tabs=8,
            error_message="Flow video options panel did not open correctly.",
        )

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
            return f"Flow da submit video nhung server tra Failed o khoang {match.group(1)}%."
        return "Flow da submit video nhung server tra Failed."

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
        project_url = self._project_root_url(page.url)

        video_count = await page.locator("video").count()
        if video_count == 0:
            raise RuntimeError("Flow khong hien thi video nao de tai ve.")

        total = min(requested, video_count)
        for index in range(total):
            self._ensure_not_cancelled(cancel_event)
            if self._project_root_url(page.url) != project_url:
                await page.goto(project_url, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(2500)

            self._emit_status(status_callback, f"Dang mo video {index + 1}/{total}...")
            await self._open_video_detail_from_project(page, index, cancel_event, status_callback)

            output_path = self._reserve_output_path(output_dir / f"{start_index + index + 1}-{prefix}.mp4")
            quality_text = str(download_quality or "1080p").upper()
            async with runtime.download_slot():
                if quality_text in {"2K", "4K"}:
                    self._emit_status(status_callback, f"Dang yeu cau ban upscale {quality_text} cho video {index + 1}/{total}...")
                else:
                    self._emit_status(status_callback, f"Dang tai video {index + 1}/{total}...")
                await self._download_video_from_detail(page, output_path, target_quality)

            saved_paths.append(str(output_path))
            logger.info("Saved Flow video: %s", output_path)
            self._remember_video_context(project_url=project_url, detail_url=page.url)
            self._emit_progress(progress_callback, int(((index + 1) / max(1, total)) * 100))
            self._emit_status(status_callback, f"Da tai xong video {index + 1}/{total}.")

        return saved_paths

    async def _download_current_video_detail(
        self,
        runtime: FlowBrowserRuntime,
        page,
        output_path: Path,
        download_quality: str,
        cancel_event: asyncio.Event | None,
        progress_callback=None,
        status_callback=None,
    ) -> str:
        self._ensure_not_cancelled(cancel_event)
        output_path = self._reserve_output_path(output_path)
        quality_text = str(download_quality or "1080p").upper()
        target_quality = self._video_quality_label(download_quality)

        async with runtime.download_slot():
            if quality_text in {"2K", "4K"}:
                self._emit_status(status_callback, f"Dang yeu cau ban upscale {quality_text} cho video keo dai...")
            else:
                self._emit_status(status_callback, "Dang tai video keo dai...")
            await self._download_video_from_detail(page, output_path, target_quality)

        self._remember_video_context(project_url=self._project_root_url(page.url), detail_url=page.url)
        self._emit_progress(progress_callback, 100)
        self._emit_status(status_callback, "Da tai xong video keo dai.")
        return str(output_path)

    async def _download_video_from_detail(self, page, output_path: Path, target_quality: str) -> None:
        download_button = page.get_by_role("button", name="Download").first
        await download_button.wait_for(timeout=60000)
        await download_button.click(force=True)
        await page.wait_for_timeout(500)
        menu_items = page.locator('[role="menuitem"]')
        if await menu_items.count():
            await self._open_video_download_submenu(page, menu_items, target_quality)
            menu_items = page.locator('[role="menuitem"]')
            async with page.expect_download(timeout=180000) as download_info:
                preferred = await self._pick_video_download_item(menu_items, target_quality)
                await preferred.click(force=True)
            download = await download_info.value
        else:
            async with page.expect_download(timeout=180000) as download_info:
                await download_button.click(force=True)
            download = await download_info.value

        await download.save_as(str(output_path))

    async def _open_video_download_submenu(self, page, menu_items, target_quality: str) -> None:
        texts = [text.strip() for text in await menu_items.all_inner_texts() if text.strip()]
        if self._menu_contains_quality(texts):
            return

        full_video = menu_items.filter(has_text="Full Video")
        if await full_video.count():
            await full_video.first.click(force=True)
            await page.wait_for_timeout(700)
            menu_items = page.locator('[role="menuitem"]')
            texts = [text.strip() for text in await menu_items.all_inner_texts() if text.strip()]
            if self._menu_contains_quality(texts):
                return

        clip_one = menu_items.filter(has_text="Clip 1")
        if await clip_one.count():
            await clip_one.first.click(force=True)
            await page.wait_for_timeout(700)

    def _menu_contains_quality(self, texts: list[str]) -> bool:
        normalized = "\n".join(texts)
        return any(label in normalized for label in ("1080p", "2K", "4K", "720p", "Original Size"))

    async def _open_latest_video_for_extend(self, page, cancel_event: asyncio.Event | None, status_callback) -> None:
        if "/edit/" in page.url and await page.get_by_role("button").filter(has_text="Extend").count():
            return

        if self._last_video_detail_url:
            await page.goto(self._last_video_detail_url, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(2500)
            if await page.get_by_role("button").filter(has_text="Extend").count():
                return

        self._emit_status(status_callback, "Dang mo clip gan nhat trong project de keo dai...")
        await self._open_video_detail_from_project(page, 0, cancel_event, status_callback)
        if await page.get_by_role("button").filter(has_text="Extend").count():
            return

        raise RuntimeError(
            "Khong tim thay clip nao trong project gan nhat de keo dai. Hay tao 1 video thanh cong roi thu lai."
        )

    async def _open_video_detail_from_project(
        self,
        page,
        index: int,
        cancel_event: asyncio.Event | None,
        status_callback,
    ) -> None:
        project_url = self._project_root_url(page.url)
        for _ in range(8):
            self._ensure_not_cancelled(cancel_event)
            hrefs = await page.locator('a[href*="/edit/"]').evaluate_all(
                """
                (elements) => elements
                  .map((element) => element.getAttribute('href') || '')
                  .filter((href) => href.includes('/edit/'))
                """
            )
            if len(hrefs) > index:
                detail_url = urljoin(page.url, hrefs[index])
                self._emit_status(status_callback, f"Dang mo trang chi tiet video {index + 1}...")
                await page.goto(detail_url, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(2500)
                if await page.get_by_role("button", name="Download").count():
                    self._remember_video_context(project_url=project_url, detail_url=page.url)
                    return

            play_text = page.get_by_text("play_circle")
            if await play_text.count() > index:
                self._emit_status(status_callback, f"Dang mo overlay video {index + 1}...")
                await play_text.nth(index).click(force=True)
                await page.wait_for_timeout(2500)
                if await page.get_by_role("button", name="Download").count():
                    self._remember_video_context(project_url=project_url, detail_url=page.url)
                    return

            if self._project_root_url(page.url) != project_url:
                await page.goto(project_url, wait_until="domcontentloaded", timeout=120000)
                await page.wait_for_timeout(1500)
            else:
                await page.wait_for_timeout(1500)

        raise RuntimeError("Khong mo duoc trang chi tiet video de tai ve.")

    async def _wait_for_extend_result(
        self,
        page,
        cancel_event: asyncio.Event | None,
        progress_callback=None,
        status_callback=None,
    ) -> None:
        seen_progress = False
        stable_failed_seconds = 0
        ready_without_progress = 0
        last_progress = -1
        baseline_video_count = await page.locator("video").count()

        for _ in range(180):
            self._ensure_not_cancelled(cancel_event)
            await page.wait_for_timeout(5000)
            body = await page.locator("body").inner_text()
            progress = self._extract_progress(body)
            video_count = await page.locator("video").count()
            has_failed = "Failed" in body or "Something went wrong." in body

            if progress is not None:
                seen_progress = True
                ready_without_progress = 0
                stable_failed_seconds = 0
                if progress >= last_progress:
                    last_progress = progress
                    self._emit_progress(progress_callback, progress)
                self._emit_status(status_callback, f"Flow dang keo dai video: {progress}%")
            elif seen_progress:
                ready_without_progress += 1
                self._emit_status(status_callback, "Flow dang hoan tat video keo dai...")
                if video_count > baseline_video_count:
                    self._emit_progress(progress_callback, 95)
                    self._emit_status(status_callback, "Flow da render xong video keo dai. Chuan bi tai...")
                    return
                if ready_without_progress >= 3 and not has_failed:
                    self._emit_progress(progress_callback, 95)
                    self._emit_status(status_callback, "Flow da render xong video keo dai. Chuan bi tai...")
                    return
            else:
                self._emit_status(status_callback, "Flow dang chuan bi video keo dai...")

            if has_failed and not seen_progress:
                stable_failed_seconds += 5
                if stable_failed_seconds >= 180:
                    raise RuntimeError(self._format_failure(body))
            else:
                stable_failed_seconds = 0

        raise RuntimeError("Flow chua hoan tat video keo dai trong thoi gian cho.")

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
                self._emit_status(status_callback, f"Flow dang render video: {progress}%")
            elif progress is None:
                self._emit_status(status_callback, "Flow dang xep hang hoac render video...")

            if video_count:
                if video_count >= requested:
                    self._emit_progress(progress_callback, 95)
                    self._emit_status(status_callback, f"Flow da render du {requested}/{requested} video. Chuan bi tai...")
                    return
                self._emit_progress(progress_callback, min(92, 80 + int((video_count / max(1, requested)) * 12)))
                self._emit_status(
                    status_callback,
                    f"Flow da render {video_count}/{requested} video. App dang cho du so luong...",
                )

            has_failed = "Failed" in body or "Something went wrong." in body
            if has_failed:
                stable_failed_seconds += 5
                if stable_failed_seconds >= max_failed_grace_seconds:
                    raise RuntimeError(self._format_failure(body))
                self._emit_status(
                    status_callback,
                    "Flow dang bao trang thai chua on dinh. App tiep tuc cho them de tranh fail som...",
                )
            else:
                stable_failed_seconds = 0

        if last_video_count:
            raise RuntimeError(f"Flow chi render duoc {last_video_count}/{requested} video.")
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

    def _project_root_url(self, url: str) -> str:
        return str(url).split("/edit/")[0]

    def _load_last_video_context(self) -> tuple[str | None, str | None]:
        if not LAST_VIDEO_CONTEXT_FILE.exists():
            return None, None
        try:
            data = json.loads(LAST_VIDEO_CONTEXT_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, None
        if not isinstance(data, dict):
            return None, None
        project_url = str(data.get("project_url") or "").strip() or None
        detail_url = str(data.get("detail_url") or "").strip() or None
        return project_url, detail_url

    def _remember_video_context(self, project_url: str | None = None, detail_url: str | None = None) -> None:
        if project_url is not None:
            project_url = str(project_url or "").strip() or None
            self._last_video_project_url = project_url
        if detail_url is not None:
            detail_url = str(detail_url or "").strip() or None
            self._last_video_detail_url = detail_url

        payload = {
            "project_url": self._last_video_project_url,
            "detail_url": self._last_video_detail_url,
        }
        LAST_VIDEO_CONTEXT_FILE.parent.mkdir(parents=True, exist_ok=True)
        LAST_VIDEO_CONTEXT_FILE.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def _pick_video_download_item(self, menu_items, target_quality: str):
        normalized_target = str(target_quality or "1080p").strip().lower()
        if normalized_target == "4k":
            priorities = ["4K", "2K", "1080p", "720p", "Original Size"]
        elif normalized_target == "2k":
            priorities = ["2K", "1080p", "720p", "Original Size"]
        else:
            priorities = ["1080p", "720p", "Original Size"]
        for target in priorities:
            candidate = menu_items.filter(has_text=target)
            if await candidate.count():
                return candidate.first
        return menu_items.first
