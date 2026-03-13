"""Base QThread worker helpers."""

from __future__ import annotations

import asyncio
import logging
from abc import abstractmethod

from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class BaseWorker(QThread):
    """Run an async coroutine inside a dedicated Qt worker thread."""

    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int)
    status = Signal(str)
    cancelled = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._loop = None
        self._task = None
        self.cancel_event = None

    @abstractmethod
    async def _run_async(self):
        """Implement the async body in subclasses."""

    def run(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        self.cancel_event = asyncio.Event()
        asyncio.set_event_loop(loop)
        try:
            self._task = loop.create_task(self._run_async())
            result = loop.run_until_complete(self._task)
            self.finished.emit(result)
        except asyncio.CancelledError:
            self.cancelled.emit("Đã dừng tác vụ.")
        except Exception as exc:
            logger.error("%s error: %s", self.__class__.__name__, exc)
            self.error.emit(str(exc))
        finally:
            self._task = None
            self.cancel_event = None
            self._loop = None
            loop.close()

    def request_cancel(self) -> None:
        if self.cancel_event is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self.cancel_event.set)
        if self._task is not None and self._loop is not None:
            self._loop.call_soon_threadsafe(self._task.cancel)
