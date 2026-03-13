"""Shared generator logic."""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime

from core.labs_api import LabsAPIClient

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """Common polling, tracking, and naming logic for all generators."""

    def __init__(self, api_client: LabsAPIClient, poll_interval: int) -> None:
        self.api = api_client
        self.poll_interval = poll_interval
        self.jobs: list[dict] = []

    @abstractmethod
    async def generate(self, prompt: str, account_id: str, **kwargs: object) -> dict:
        """Run submit, poll, and download for a single job."""

    async def _poll_until_done(
        self,
        account_id: str,
        generation_id: str,
        timeout: int,
    ) -> list[str] | None:
        elapsed = 0
        while elapsed < timeout:
            status_data = await self.api.get_status(account_id, generation_id)
            status = status_data["status"]
            logger.info(
                "Poll %s: %s (%s%%) [%ss/%ss]",
                generation_id[:8],
                status,
                status_data.get("progress", 0),
                elapsed,
                timeout,
            )
            if status == "COMPLETED":
                return status_data.get("media_urls")
            if status == "FAILED":
                logger.error("Generation failed: %s", status_data.get("error"))
                return None
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval
        logger.warning("Timeout after %ss for %s", timeout, generation_id[:8])
        return None

    def _create_job(self, prompt: str, account_id: str) -> dict:
        return {
            "prompt": prompt,
            "account_id": account_id,
            "status": "pending",
            "output_paths": [],
            "error": None,
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
        }

    def _record_job(self, job: dict) -> None:
        job["completed_at"] = datetime.now().isoformat()
        self.jobs.append(job)

    def get_jobs(self) -> list[dict]:
        return list(self.jobs)

    @staticmethod
    def _safe_filename(text: str, max_len: int = 50) -> str:
        safe = re.sub(r"[^\w\s-]", "", text)
        safe = re.sub(r"\s+", "_", safe.strip())
        return safe[:max_len] or "untitled"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _indexed_prefix(prefix: str, index: int) -> str:
        return f"{index + 1}-{prefix}"
