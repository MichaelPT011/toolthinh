"""Video generator."""

from __future__ import annotations

import asyncio
import logging

from core.base_generator import BaseGenerator
from core.config import OUTPUT_VIDEOS, VIDEO_TIMEOUT

logger = logging.getLogger(__name__)


class VideoGenerator(BaseGenerator):
    """Video generation using the configured backend."""

    def __init__(self, api_client, poll_interval: int = 5, browser_assist=None, video_automation=None) -> None:
        super().__init__(api_client, poll_interval)
        self.output_dir = OUTPUT_VIDEOS
        self.browser_assist = browser_assist
        self.video_automation = video_automation

    def create_shared_runtime(self, max_concurrent: int = 1):
        if self.video_automation:
            return self.video_automation.create_shared_runtime(max_concurrent)
        return None

    async def generate(
        self,
        prompt: str,
        account_id: str,
        aspect_ratio: str = "16:9",
        image_path: str | None = None,
        duration: str = "8s",
        num_outputs: int = 1,
        download_quality: str = "1080p",
        mode: str = "text",
        start_image_path: str | None = None,
        end_image_path: str | None = None,
        ingredient_paths: list[str] | None = None,
        extend_video_path: str | None = None,
        launch_browser: bool = True,
        shared_runtime=None,
        cancel_event=None,
        progress_callback=None,
        status_callback=None,
    ) -> dict:
        if self.video_automation and shared_runtime is None:
            async with self.video_automation.create_shared_runtime(1) as runtime:
                return await self.generate(
                    prompt,
                    account_id,
                    aspect_ratio=aspect_ratio,
                    image_path=image_path,
                    duration=duration,
                    num_outputs=num_outputs,
                    download_quality=download_quality,
                    mode=mode,
                    start_image_path=start_image_path,
                    end_image_path=end_image_path,
                    ingredient_paths=ingredient_paths,
                    extend_video_path=extend_video_path,
                    launch_browser=launch_browser,
                    shared_runtime=runtime,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                )

        job = self._create_job(prompt, account_id)
        try:
            last_error = ""
            for attempt in range(1, 11):
                job["attempts"] = attempt
                job["output_paths"] = []
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError()
                if status_callback:
                    status_callback(f"Đang thử tạo video lần {attempt}/10...")

                try:
                    if self.video_automation:
                        stamp = self._timestamp()
                        safe = self._safe_filename(prompt)
                        job["output_paths"] = await self.video_automation.generate_videos(
                            prompt,
                            self.output_dir,
                            f"video_{safe}_{stamp}",
                            aspect_ratio=aspect_ratio,
                            duration=duration,
                            num_outputs=num_outputs,
                            download_quality=download_quality,
                            mode=mode,
                            image_path=image_path,
                            start_image_path=start_image_path,
                            end_image_path=end_image_path,
                            ingredient_paths=ingredient_paths,
                            extend_video_path=extend_video_path,
                            runtime=shared_runtime,
                            cancel_event=cancel_event,
                            progress_callback=progress_callback,
                            status_callback=status_callback,
                        )
                        job["status"] = "completed"
                        break

                    if self.browser_assist:
                        stamp = self._timestamp()
                        safe = self._safe_filename(prompt)
                        expected_count = max(1, min(int(num_outputs or 1), 4))
                        media_paths = [
                            path
                            for path in [image_path, start_image_path, end_image_path, extend_video_path]
                            if path
                        ]
                        media_paths.extend(path for path in (ingredient_paths or []) if path)
                        if launch_browser:
                            self.browser_assist.launch_tool("video", prompt, media_paths or None)
                        if status_callback:
                            status_callback(f"Đang chờ Flow tải video về... (lần {attempt}/10)")
                        downloads = await self.browser_assist.wait_for_downloads(
                            {".mp4", ".mov", ".webm"},
                            VIDEO_TIMEOUT,
                            expected_count=expected_count,
                        )
                        if not downloads:
                            raise RuntimeError("Flow không trả về đủ video để tải.")
                        job["output_paths"] = self.browser_assist.import_downloads(
                            downloads[:expected_count],
                            self.output_dir,
                            f"video_{safe}_{stamp}",
                        )
                        if progress_callback:
                            progress_callback(100)
                        job["status"] = "completed"
                        break

                    result = await self.api.submit_video(account_id, prompt, aspect_ratio, image_path, duration)
                    generation_id = result["generation_id"]
                    media_urls = await self._poll_until_done(account_id, generation_id, VIDEO_TIMEOUT)
                    if not media_urls:
                        raise RuntimeError("Video bị timeout khi chờ Flow trả kết quả.")
                    stamp = self._timestamp()
                    safe = self._safe_filename(prompt)
                    for index, url in enumerate(media_urls):
                        path = str(self.output_dir / f"{index + 1}-video_{safe}_{stamp}.mp4")
                        await self.api.download_media(account_id, url, path)
                        job["output_paths"].append(path)
                    job["status"] = "completed"
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    last_error = str(exc)
                    logger.error("Video generation attempt %s failed: %s", attempt, exc)
                    if attempt >= 10:
                        raise
                    if status_callback:
                        status_callback(f"Lần {attempt}/10 lỗi, đang tự thử lại...")
                    if progress_callback:
                        progress_callback(0)

            job["requested_mode"] = mode
            job["requested_quality"] = download_quality
            if job.get("status") != "completed":
                raise RuntimeError(last_error or "Video generation failed.")
        except Exception as exc:
            logger.error("Video generation failed: %s", exc)
            job["status"] = "failed"
            job["error"] = str(exc)
        self._record_job(job)
        return job
