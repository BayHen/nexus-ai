"""OpenTelemetry provider configuration without sensitive payload attributes."""

from dataclasses import dataclass

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from nexus.bootstrap.config import Settings
from nexus.platform.observability.metrics import ApplicationMetrics


@dataclass(slots=True)
class Telemetry:
    metrics: ApplicationMetrics
    tracer_provider: TracerProvider

    def shutdown(self) -> None:
        self.tracer_provider.shutdown()


def configure_telemetry(settings: Settings) -> Telemetry:
    """Create process-local metrics and a bounded OTLP trace pipeline."""
    provider = TracerProvider(
        resource=Resource.create(
            {
                "service.name": "nexus-api",
                "service.version": settings.app_version,
                "deployment.environment.name": settings.environment,
            }
        ),
        sampler=ParentBased(TraceIdRatioBased(settings.otel_trace_sample_ratio)),
    )
    if settings.otel_exporter_otlp_endpoint:
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.otel_exporter_otlp_endpoint,
                    insecure=settings.otel_exporter_otlp_endpoint.startswith("http://"),
                )
            )
        )
    return Telemetry(ApplicationMetrics(), provider)
