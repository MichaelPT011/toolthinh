"""Safe backend abstraction and local mock implementation."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from core.google_auth import GoogleAuth

logger = logging.getLogger(__name__)


class LabsAPIError(Exception):
    """Base exception for backend failures."""


class AuthExpiredError(LabsAPIError):
    """Raised when a configured profile becomes invalid."""


class RateLimitError(LabsAPIError):
    """Raised when the backend asks the caller to retry later."""


class GenerationFailedError(LabsAPIError):
    """Raised when a generation does not finish successfully."""


class MockLabsBackend:
    """Generate local placeholder media while preserving async app flows."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict] = {}
        self._ffmpeg = shutil.which("ffmpeg")

    async def check_session(self, account: dict) -> dict:
        await asyncio.sleep(0.1)
        return {
            "status": "active",
            "email": account.get("email") or f"{account.get('nickname', 'profile')}@local.demo",
            "user_name": account.get("user_name") or account.get("nickname") or "Profile",
        }

    async def submit_video(
        self,
        account_id: str,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_path: str | None = None,
        duration: str = "8s",
    ) -> dict:
        generation_id = str(uuid.uuid4())
        self._jobs[generation_id] = {
            "kind": "video",
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "duration": duration,
            "image_path": image_path,
            "created_at": time.monotonic(),
            "ready_after": 5.0,
            "count": 1,
            "account_id": account_id,
        }
        return {"generation_id": generation_id, "status": "PENDING"}

    async def submit_flow(
        self,
        account_id: str,
        prompt: str,
        image_path: str | None = None,
        num_images: int = 4,
    ) -> dict:
        generation_id = str(uuid.uuid4())
        self._jobs[generation_id] = {
            "kind": "image",
            "prompt": prompt,
            "image_path": image_path,
            "created_at": time.monotonic(),
            "ready_after": 2.0,
            "count": max(1, num_images),
            "account_id": account_id,
        }
        return {"generation_id": generation_id, "status": "PENDING"}

    async def submit_whisk(
        self,
        account_id: str,
        prompt: str,
        subject_image_path: str,
        style_image_path: str,
        seed: int | None = None,
    ) -> dict:
        generation_id = str(uuid.uuid4())
        self._jobs[generation_id] = {
            "kind": "whisk",
            "prompt": prompt,
            "subject_image_path": subject_image_path,
            "style_image_path": style_image_path,
            "seed": seed,
            "created_at": time.monotonic(),
            "ready_after": 2.0,
            "count": 1,
            "account_id": account_id,
        }
        return {"generation_id": generation_id, "status": "PENDING"}

    async def get_status(self, account_id: str, generation_id: str) -> dict:
        job = self._jobs.get(generation_id)
        if not job or job.get("account_id") != account_id:
            raise GenerationFailedError(f"Unknown generation id: {generation_id}")

        elapsed = time.monotonic() - job["created_at"]
        ratio = min(max(elapsed / job["ready_after"], 0.0), 1.0)
        if ratio < 0.2:
            status = "PENDING"
        elif ratio < 1.0:
            status = "GENERATING"
        else:
            status = "COMPLETED"

        urls = None
        if status == "COMPLETED":
            urls = [f"mock://{generation_id}/{index}" for index in range(job["count"])]

        return {
            "status": status,
            "progress": int(ratio * 100),
            "media_urls": urls,
            "error": None,
        }

    async def download_media(self, account_id: str, url: str, output_path: str) -> str:
        del account_id
        if not url.startswith("mock://"):
            raise LabsAPIError(f"Unsupported media URL: {url}")
        generation_id = url.removeprefix("mock://").split("/", 1)[0]
        job = self._jobs.get(generation_id)
        if not job:
            raise GenerationFailedError(f"Unknown generation id: {generation_id}")
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._write_mock_media, job, output)
        return str(output)

    def _write_mock_media(self, job: dict, output_path: Path) -> None:
        if job["kind"] == "video":
            self._create_mock_video(output_path, job["prompt"], job.get("duration") or "8s")
        else:
            self._create_mock_image(output_path, job["prompt"], job["kind"])

    def _create_mock_image(self, output_path: Path, prompt: str, kind: str) -> None:
        if not self._ffmpeg:
            output_path.write_text(
                "Image placeholder could not be rendered because ffmpeg was not found.\n"
                f"Kind: {kind}\nPrompt: {prompt}\n",
                encoding="utf-8",
            )
            return
        cmd = [
            self._ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=#17212b:s=1280x720",
            "-frames:v",
            "1",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        output_path.with_suffix(output_path.suffix + ".txt").write_text(
            f"Kind: {kind}\nPrompt: {prompt}\n",
            encoding="utf-8",
        )

    def _create_mock_video(self, output_path: Path, prompt: str, duration: str) -> None:
        seconds = 4
        if duration.endswith("s") and duration[:-1].isdigit():
            seconds = max(1, int(duration[:-1]))

        if not self._ffmpeg:
            output_path.write_text(
                "Video placeholder could not be rendered because ffmpeg was not found.\n"
                f"Prompt: {prompt}\n",
                encoding="utf-8",
            )
            return

        with tempfile.TemporaryDirectory(prefix="veo3_safe_") as tmp_dir:
            cmd = [
                self._ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=#17212b:s=1280x720:d={seconds}",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-t",
                str(seconds),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-shortest",
                str(output_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
        output_path.with_suffix(output_path.suffix + ".txt").write_text(
            f"Kind: video\nPrompt: {prompt}\nDuration: {seconds}s\n",
            encoding="utf-8",
        )


class LabsAPIClient:
    """Public API surface used by the generators."""

    def __init__(self, auth: GoogleAuth, backend: MockLabsBackend | None = None) -> None:
        self.auth = auth
        self.backend = backend or MockLabsBackend()

    async def submit_video(
        self,
        account_id: str,
        prompt: str,
        aspect_ratio: str = "16:9",
        image_path: str | None = None,
        duration: str = "8s",
    ) -> dict:
        return await self.backend.submit_video(account_id, prompt, aspect_ratio, image_path, duration)

    async def submit_flow(
        self,
        account_id: str,
        prompt: str,
        image_path: str | None = None,
        num_images: int = 4,
    ) -> dict:
        return await self.backend.submit_flow(account_id, prompt, image_path, num_images)

    async def submit_whisk(
        self,
        account_id: str,
        prompt: str,
        subject_image_path: str,
        style_image_path: str,
        seed: int | None = None,
    ) -> dict:
        return await self.backend.submit_whisk(account_id, prompt, subject_image_path, style_image_path, seed)

    async def get_status(self, account_id: str, generation_id: str) -> dict:
        return await self.backend.get_status(account_id, generation_id)

    async def download_media(self, account_id: str, url: str, output_path: str) -> str:
        return await self.backend.download_media(account_id, url, output_path)

    async def check_session(self, account_id: str) -> dict:
        account = self.auth.get_account(account_id)
        if not account:
            raise AuthExpiredError("Unknown profile")
        return await self.backend.check_session(account)
