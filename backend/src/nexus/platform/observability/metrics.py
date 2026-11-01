"""Prometheus metrics with deliberately bounded labels."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5)
DB_BUCKETS = (0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5)


class ApplicationMetrics:
    """Own one isolated registry so app factories remain test-safe."""

    def __init__(self) -> None:
        self.registry = CollectorRegistry(auto_describe=True)
        self.http_requests = Counter(
            "nexus_http_requests_total",
            "Completed HTTP requests.",
            ("method", "route", "status_code"),
            registry=self.registry,
        )
        self.http_duration = Histogram(
            "nexus_http_request_duration_seconds",
            "HTTP request latency.",
            ("method", "route"),
            buckets=HTTP_BUCKETS,
            registry=self.registry,
        )
        self.http_in_progress = Gauge(
            "nexus_http_requests_in_progress",
            "HTTP requests currently executing.",
            registry=self.registry,
        )
        self.db_operations = Counter(
            "nexus_db_operations_total",
            "Database operations by bounded operation and outcome.",
            ("operation", "status"),
            registry=self.registry,
        )
        self.db_duration = Histogram(
            "nexus_db_operation_duration_seconds",
            "Database operation latency without SQL text or bind values.",
            ("operation",),
            buckets=DB_BUCKETS,
            registry=self.registry,
        )
        self.db_connections = Gauge(
            "nexus_db_connections_checked_out",
            "Checked-out SQLAlchemy pool connections.",
            registry=self.registry,
        )
        self.dependency_ready = Gauge(
            "nexus_dependency_ready",
            "Dependency readiness where one is ready and zero is unavailable.",
            ("dependency",),
            registry=self.registry,
        )

    def observe_http(self, method: str, route: str, status_code: int, seconds: float) -> None:
        self.http_requests.labels(method, route, str(status_code)).inc()
        self.http_duration.labels(method, route).observe(seconds)

    def observe_database(self, operation: str, status: str, seconds: float) -> None:
        self.db_operations.labels(operation, status).inc()
        self.db_duration.labels(operation).observe(seconds)
