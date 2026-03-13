"""Batch execution helpers."""

from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack
from enum import Enum


class BatchMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class BatchJob:
    """One item in the batch queue."""

    def __init__(self, prompt: str, gen_type: str = "video", **kwargs: object) -> None:
        self.prompt = prompt
        self.gen_type = gen_type
        self.kwargs = kwargs
        self.status = "pending"
        self.result = None
        self.error = None


class BatchEngine:
    """Run generation jobs sequentially or in parallel."""

    def __init__(self) -> None:
        self.queue: list[BatchJob] = []
        self.is_running = False
        self._cancel_flag = False

    def add_job(self, job: BatchJob) -> None:
        self.queue.append(job)

    def clear(self) -> None:
        self.queue.clear()

    def cancel(self) -> None:
        self._cancel_flag = True

    async def run(
        self,
        generators: dict,
        auth,
        mode: BatchMode = BatchMode.SEQUENTIAL,
        max_concurrent: int = 1,
        interval: int = 2,
        on_progress=None,
        on_status=None,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        self.is_running = True
        self._cancel_flag = False
        try:
            async with AsyncExitStack() as stack:
                runtime_map = {}
                for gen_type, generator in generators.items():
                    runtime_factory = getattr(generator, "create_shared_runtime", None)
                    if not runtime_factory:
                        continue
                    shared_runtime = runtime_factory(1 if mode == BatchMode.SEQUENTIAL else max_concurrent)
                    if shared_runtime is not None:
                        runtime_map[gen_type] = await stack.enter_async_context(shared_runtime)
                if mode == BatchMode.SEQUENTIAL:
                    await self._run_sequential(generators, auth, interval, on_progress, on_status, runtime_map, cancel_event)
                else:
                    await self._run_parallel(generators, auth, max_concurrent, on_progress, on_status, runtime_map, cancel_event)
        finally:
            self.is_running = False

    async def _run_sequential(self, generators, auth, interval: int, on_progress, on_status, runtime_map, cancel_event) -> None:
        for index, job in enumerate(self.queue):
            if self._cancel_flag or (cancel_event and cancel_event.is_set()):
                job.status = "cancelled"
                if on_progress:
                    on_progress(index, job)
                continue

            job.status = "running"
            if on_status:
                on_status(index, "Đang khởi tạo...", "")
            account = auth.get_next_active_account()
            if not account:
                job.status = "failed"
                job.error = "No active account"
                if on_progress:
                    on_progress(index, job)
                continue

            generator = generators.get(job.gen_type)
            if not generator:
                job.status = "failed"
                job.error = f"Unknown generator: {job.gen_type}"
                if on_progress:
                    on_progress(index, job)
                continue

            try:
                def status_callback(text: str) -> None:
                    job.status = text
                    if on_status:
                        on_status(index, text, "")

                def progress_callback(value: int) -> None:
                    text = f"Đang chạy {value}%"
                    job.status = text
                    if on_status:
                        on_status(index, text, "")

                result = await generator.generate(
                    job.prompt,
                    account["account_id"],
                    shared_runtime=runtime_map.get(job.gen_type),
                    cancel_event=cancel_event,
                    progress_callback=progress_callback,
                    status_callback=status_callback,
                    **job.kwargs,
                )
                job.status = result.get("status", "completed")
                job.result = result
            except asyncio.CancelledError:
                job.status = "cancelled"
            except Exception as exc:
                job.status = "failed"
                job.error = str(exc)

            if on_progress:
                on_progress(index, job)

            if index < len(self.queue) - 1 and not self._cancel_flag and not (cancel_event and cancel_event.is_set()):
                await asyncio.sleep(interval)

    async def _run_parallel(self, generators, auth, max_concurrent: int, on_progress, on_status, runtime_map, cancel_event) -> None:
        semaphore = asyncio.Semaphore(max_concurrent)

        async def run_one(index: int, job: BatchJob) -> None:
            async with semaphore:
                if self._cancel_flag or (cancel_event and cancel_event.is_set()):
                    job.status = "cancelled"
                    if on_progress:
                        on_progress(index, job)
                    return

                job.status = "running"
                if on_status:
                    on_status(index, "Đang khởi tạo...", "")
                account = auth.get_next_active_account()
                if not account:
                    job.status = "failed"
                    job.error = "No active account"
                    if on_progress:
                        on_progress(index, job)
                    return

                generator = generators.get(job.gen_type)
                if not generator:
                    job.status = "failed"
                    job.error = f"Unknown generator: {job.gen_type}"
                    if on_progress:
                        on_progress(index, job)
                    return

                try:
                    def status_callback(text: str) -> None:
                        job.status = text
                        if on_status:
                            on_status(index, text, "")

                    def progress_callback(value: int) -> None:
                        text = f"Đang chạy {value}%"
                        job.status = text
                        if on_status:
                            on_status(index, text, "")

                    result = await generator.generate(
                        job.prompt,
                        account["account_id"],
                        shared_runtime=runtime_map.get(job.gen_type),
                        cancel_event=cancel_event,
                        progress_callback=progress_callback,
                        status_callback=status_callback,
                        **job.kwargs,
                    )
                    job.status = result.get("status", "completed")
                    job.result = result
                except asyncio.CancelledError:
                    job.status = "cancelled"
                except Exception as exc:
                    job.status = "failed"
                    job.error = str(exc)

                if on_progress:
                    on_progress(index, job)

        await asyncio.gather(*(run_one(index, job) for index, job in enumerate(self.queue)))
