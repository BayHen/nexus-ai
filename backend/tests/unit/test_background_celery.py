"""Celery queue topology tests without contacting the broker."""

import pytest

from nexus.bootstrap.config import Settings


def test_celery_uses_durable_main_and_dead_letter_queues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+asyncpg://unused:unused@127.0.0.1:1/unused"
    )
    monkeypatch.setenv(
        "JWT_SECRET_KEY", "test-secret-key-that-is-at-least-32-characters"
    )
    from nexus.platform.background.celery_app import create_celery_app

    settings = Settings(
        environment="test",
        database_url="postgresql+asyncpg://unused:unused@127.0.0.1:1/unused",
        jwt_secret_key="test-secret-key-that-is-at-least-32-characters",
        celery_broker_url="amqp://worker:secret@127.0.0.1:5672//",
        celery_result_backend="redis://127.0.0.1:6379/1",
        _env_file=None,
    )
    application = create_celery_app(settings)
    queues = {queue.name: queue for queue in application.conf.task_queues}

    assert queues["nexus.jobs"].durable is True
    assert queues["nexus.jobs.dead"].durable is True
    assert queues["nexus.jobs"].queue_arguments == {
        "x-dead-letter-exchange": "nexus.jobs.dead",
        "x-dead-letter-routing-key": "dead",
    }
    assert application.conf.task_acks_late is True
    assert application.conf.task_reject_on_worker_lost is True
