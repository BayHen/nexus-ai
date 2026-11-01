"""Deterministic FastAPI target for HTTP overhead benchmarks."""

from nexus.bootstrap.application import create_app
from nexus.bootstrap.config import Settings


class BenchmarkDatabaseManager:
    """Healthy lifecycle double; benchmark endpoints do not open transactions."""

    async def check_connection(self) -> bool:
        return True

    async def dispose(self) -> None:
        return None


settings = Settings(
    environment="test",
    log_level="ERROR",
    database_url="postgresql+asyncpg://synthetic:synthetic@127.0.0.1:1/synthetic",
    jwt_secret_key="synthetic-benchmark-secret-at-least-32-characters",
    _env_file=None,
)
app = create_app(settings, database_manager=BenchmarkDatabaseManager())
