"""Image generator."""

from __future__ import annotations

import asyncio

from core.base_generator import BaseGenerator
from core.config import IMAGE_TIMEOUT, OUTPUT_IMAGES


class FlowGenerator(BaseGenerator):
    """Image generation using the configured backend."""

    def __init__(self, api_client, poll_interval: int = 2, browser_assist=None, flow_automation=None) -> None:
        super().__init__(api_client, poll_interval)
        self.output_dir = OUTPUT_IMAGES
        self.browser_assist = browser_assist
        self.flow_automation = flow_automation

    def create_shared_runtime(self, max_concurrent: int = 1):
        if self.flow_automation:
            return self.flow_automation.create_shared_runtime(max_concurrent)
        return None

    async def generate(
        self,
        prompt: str,
        account_id: str,
        image_path: str | None = None,
        num_images: int = 1,
        download_quality: str = "1080p",
        orientation: str = "landscape",
        launch_browser: bool = True,
        shared_runtime=None,
        cancel_event=None,
        progress_callback=None,
        status_callback=None,
    ) -> dict:
        if self.flow_automation and shared_runtime is None:
            async with self.flow_automation.create_shared_runtime(1) as runtime:
                return await self.generate(
                    prompt,
                    account_id,
                    image_path=image_path,
                    num_images=num_images,
                    download_quality=download_quality,
                    orientation=orientation,
                    launch_browser=launch_browser,
                    shared_runtime=runtime,
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                )

        job = self._create_job(prompt, account_id)
        try:
            if self.flow_automation:
                last_error = ""
                for attempt in range(1, 4):
                    job["attempts"] = attempt
                    job["output_paths"] = []
                    if cancel_event and cancel_event.is_set():
                        raise asyncio.CancelledError()
                    if status_callback:
                        status_callback(f"Đang thử tạo ảnh lần {attempt}/3...")
                    try:
                        stamp = self._timestamp()
                        safe = self._safe_filename(prompt)
                        job["output_paths"] = await self.flow_automation.generate_images(
                            prompt,
                            self.output_dir,
                            f"image_{safe}_{stamp}",
                            num_images=num_images,
                            download_quality=download_quality,
                            orientation=orientation,
                            image_path=image_path,
                            runtime=shared_runtime,
                            cancel_event=cancel_event,
                            progress_callback=progress_callback,
                            status_callback=status_callback,
                        )
                        job["status"] = "completed"
                        self._record_job(job)
                        return job
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        last_error = str(exc)
                        if attempt >= 3:
                            raise
                        if status_callback:
                            status_callback(f"Lần {attempt}/3 lỗi, app đang tự thử lại ảnh...")
                        if progress_callback:
                            progress_callback(0)
                raise RuntimeError(last_error or "Image generation failed.")

            if self.browser_assist:
                stamp = self._timestamp()
                safe = self._safe_filename(prompt)
                if launch_browser:
                    self.browser_assist.launch_tool("flow", prompt, [image_path] if image_path else None)
                if status_callback:
                    status_callback("Đang chờ Flow tải ảnh về...")
                downloads = await self.browser_assist.wait_for_downloads(
                    {".png", ".jpg", ".jpeg", ".webp"},
                    IMAGE_TIMEOUT,
                    expected_count=max(1, min(int(num_images or 1), 4)),
                )
                if not downloads:
                    job["status"] = "timeout"
                    self._record_job(job)
                    return job
                job["output_paths"] = self.browser_assist.import_downloads(
                    downloads,
                    self.output_dir,
                    f"image_{safe}_{stamp}",
                )
                if progress_callback:
                    progress_callback(100)
                job["status"] = "completed"
                self._record_job(job)
                return job

            result = await self.api.submit_flow(account_id, prompt, image_path, num_images)
            generation_id = result["generation_id"]
            media_urls = await self._poll_until_done(account_id, generation_id, IMAGE_TIMEOUT)
            if not media_urls:
                job["status"] = "timeout"
                self._record_job(job)
                return job
            stamp = self._timestamp()
            safe = self._safe_filename(prompt)
            for index, url in enumerate(media_urls):
                path = str(self.output_dir / f"{index + 1}-image_{safe}_{stamp}.png")
                await self.api.download_media(account_id, url, path)
                job["output_paths"].append(path)
            job["status"] = "completed"
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
        self._record_job(job)
        return job
