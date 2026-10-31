"""Celery task adapters; durable state remains in PostgreSQL."""

import asyncio
import logging
from uuid import UUID

from celery import Task  # type: ignore[import-untyped]

from nexus.bootstrap.config import Settings
from nexus.platform.background.celery_app import celery_app
from nexus.platform.background.service import JobExecutor
from nexus.platform.database.manager import DatabaseManager

logger = logging.getLogger(__name__)


async def _execute_job(job_id: UUID) -> tuple[str, int, int, int]:
    settings = Settings()
    manager = DatabaseManager(
        settings.database_url.get_secret_value(),
        settings.database_connect_timeout_seconds,
    )
    try:
        async with manager.transaction() as session:
            job = await JobExecutor(session).execute(job_id)
            return (
                job.status,
                job.attempt_count,
                job.max_attempts,
                settings.background_job_retry_base_seconds,
            )
    finally:
        await manager.dispose()


@celery_app.task(  # type: ignore[untyped-decorator]
    bind=True,
    name="nexus.background.execute_job",
    max_retries=None,
    acks_late=True,
)
def execute_job(self: Task, job_id: str) -> dict[str, object]:
    """Execute one durable job and retry only while PostgreSQL says it is retryable."""
    settings = Settings()
    try:
        status, attempts, max_attempts, retry_base = asyncio.run(
            _execute_job(UUID(job_id))
        )
    except Exception as exc:
        logger.error(
            "Background job adapter failed before durable execution completed",
            extra={
                "event": "background_job_adapter_failed",
                "job_id": job_id,
                "error_type": type(exc).__name__,
            },
        )
        raise self.retry(
            exc=exc,
            countdown=settings.background_job_retry_base_seconds,
            max_retries=settings.background_job_max_attempts - 1,
        ) from exc
    if status == "retrying":
        exponent = attempts - 1 if attempts > 1 else 0
        countdown = min(retry_base * (2**exponent), 300)
        logger.warning(
            "Background job scheduled for retry",
            extra={
                "event": "background_job_retry_scheduled",
                "job_id": job_id,
                "attempt_count": attempts,
                "max_attempts": max_attempts,
                "countdown_seconds": countdown,
            },
        )
        raise self.retry(countdown=countdown, max_retries=max_attempts - 1)
    return {"job_id": job_id, "status": status, "attempt_count": attempts}


def dispatch_job(job_id: UUID) -> str:
    """Publish a committed durable job identifier to RabbitMQ."""
    result = execute_job.apply_async(args=[str(job_id)], queue="nexus.jobs")
    return str(result.id)
