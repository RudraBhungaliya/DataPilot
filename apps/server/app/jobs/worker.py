"""
Background worker: consumes queued jobs and dispatches them to handlers.
"""

import asyncio
from typing import Awaitable, Callable, Dict, Optional

from app.core.logger import logger
from app.jobs import queue
from app.jobs.service import get_job_service

Handler = Callable[[Dict], Awaitable[Dict]]


class Worker:
    """Processes background jobs from the queue."""

    def __init__(self) -> None:
        self._handlers: Dict[str, Handler] = {}
        self._running = False

    def register(self, kind: str, handler: Handler) -> None:
        self._handlers[kind] = handler

    def register_defaults(self) -> None:
        from app.jobs.handlers import execute_collection_handler, execute_workflow_handler

        self.register("workflow.execute", execute_workflow_handler)
        self.register("collection.execute", execute_collection_handler)

    async def process(self, job_id: str) -> None:
        service = get_job_service()
        job = await service.get(job_id)
        if job is None:
            logger.warning(f"Background job '{job_id}' not found; skipping.")
            return

        handler = self._handlers.get(job.kind)
        await service.mark_running(job_id)
        try:
            if handler is None:
                raise ValueError(f"No handler registered for job kind '{job.kind}'")
            result = await handler(job.payload or {})
            await service.mark_completed(job_id, result if isinstance(result, dict) else {"result": result})
            logger.info(f"Background job '{job_id}' ({job.kind}) completed.")
        except Exception as e:
            logger.error(f"Background job '{job_id}' ({job.kind}) failed: {e}", exc_info=True)
            await service.mark_failed(job_id, str(e))

    async def run_forever(self) -> None:
        self._running = True
        logger.info("Background worker started.")
        while self._running:
            try:
                job_id = await queue.dequeue(timeout=1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Worker dequeue error: {e}")
                await asyncio.sleep(0.5)
                continue
            if job_id:
                await self.process(job_id)

    def stop(self) -> None:
        self._running = False


_worker: Optional[Worker] = None


def get_worker() -> Worker:
    global _worker
    if _worker is None:
        _worker = Worker()
        _worker.register_defaults()
    return _worker
