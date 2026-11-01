"""Celery composition root and RabbitMQ queue topology."""

import os

from celery import Celery  # type: ignore[import-untyped]
from kombu import Exchange, Queue  # type: ignore[import-untyped]

from nexus.bootstrap.config import Settings
from nexus.platform.observability import worker as worker_observability  # noqa: F401


def create_celery_app(settings: Settings | None = None) -> Celery:
    broker_url = (
        settings.celery_broker_url.get_secret_value()
        if settings is not None
        else os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@127.0.0.1:5672//")
    )
    result_backend = (
        settings.celery_result_backend.get_secret_value()
        if settings is not None
        else os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
    )
    application = Celery(
        "nexus",
        broker=broker_url,
        backend=result_backend,
        include=["nexus.platform.background.tasks"],
    )
    exchange = Exchange("nexus.jobs", type="direct", durable=True)
    dead_exchange = Exchange("nexus.jobs.dead", type="direct", durable=True)
    application.conf.update(
        task_default_queue="nexus.jobs",
        task_default_exchange=exchange.name,
        task_default_routing_key="jobs",
        task_queues=(
            Queue(
                "nexus.jobs",
                exchange=exchange,
                routing_key="jobs",
                durable=True,
                queue_arguments={
                    "x-dead-letter-exchange": dead_exchange.name,
                    "x-dead-letter-routing-key": "dead",
                },
            ),
            Queue(
                "nexus.jobs.dead",
                exchange=dead_exchange,
                routing_key="dead",
                durable=True,
            ),
        ),
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_track_started=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        broker_connection_retry_on_startup=True,
        result_expires=86400,
        timezone="UTC",
        enable_utc=True,
    )
    return application


celery_app = create_celery_app()
