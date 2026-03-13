"""Whisk remix generator."""

from __future__ import annotations

from core.base_generator import BaseGenerator
from core.config import OUTPUT_WHISK, WHISK_TIMEOUT


class WhiskGenerator(BaseGenerator):
    """Whisk remix generation using the configured backend."""

    def __init__(self, api_client, poll_interval: int = 2, browser_assist=None) -> None:
        super().__init__(api_client, poll_interval)
        self.output_dir = OUTPUT_WHISK
        self.browser_assist = browser_assist

    async def generate(
        self,
        prompt: str,
        account_id: str,
        subject_image_path: str = "",
        style_image_path: str = "",
        seed: int | None = None,
        launch_browser: bool = True,
    ) -> dict:
        job = self._create_job(prompt, account_id)
        try:
            if self.browser_assist:
                stamp = self._timestamp()
                safe = self._safe_filename(prompt)
                image_paths = [path for path in [subject_image_path, style_image_path] if path]
                if launch_browser:
                    self.browser_assist.launch_tool("whisk", prompt, image_paths)
                downloads = await self.browser_assist.wait_for_downloads(
                    {".png", ".jpg", ".jpeg", ".webp"},
                    WHISK_TIMEOUT,
                )
                if not downloads:
                    job["status"] = "timeout"
                    self._record_job(job)
                    return job
                job["output_paths"] = self.browser_assist.import_downloads(
                    downloads,
                    self.output_dir,
                    f"whisk_{safe}_{stamp}",
                )
                job["status"] = "completed"
                self._record_job(job)
                return job

            result = await self.api.submit_whisk(
                account_id,
                prompt,
                subject_image_path,
                style_image_path,
                seed,
            )
            generation_id = result["generation_id"]
            media_urls = await self._poll_until_done(account_id, generation_id, WHISK_TIMEOUT)
            if not media_urls:
                job["status"] = "timeout"
                self._record_job(job)
                return job
            stamp = self._timestamp()
            safe = self._safe_filename(prompt)
            for index, url in enumerate(media_urls):
                path = str(self.output_dir / f"whisk_{safe}_{stamp}_{index}.png")
                await self.api.download_media(account_id, url, path)
                job["output_paths"].append(path)
            job["status"] = "completed"
        except Exception as exc:
            job["status"] = "failed"
            job["error"] = str(exc)
        self._record_job(job)
        return job
