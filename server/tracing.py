"""Real W3C distributed tracing for the agent's audit trail.

Run.trace_id (a random 128-bit hex id, minted when the Run row is created —
see models.py) is the trace_id half of a W3C `traceparent`. Every RunStep
that observability.record_step() writes becomes one OTel span carrying that
same trace_id, so a single agent Run — even one paused for HITL confirmation
and resumed from a *different* HTTP request — is one trace end to end, the
same way it would be if this were split across services and the id traveled
in `traceparent` headers instead of a DB column.

Span attributes follow the OTel GenAI semantic conventions
(gen_ai.operation.name, gen_ai.provider.name, gen_ai.usage.*) so the trace is
readable by any OTel-speaking backend, not just this app's own Audit tab.

Exporting is a config change, not a code change: with no
OTEL_EXPORTER_OTLP_ENDPOINT set, spans still get real trace/span ids (stored
on Run/RunStep for the Audit tab) but nothing leaves the process. Set that
env var and spans also ship via OTLP/HTTP to Jaeger, Tempo, Langfuse, etc.
"""

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanContext, Status, StatusCode, TraceFlags

# Placeholder parent span id for the synthetic trace root. It is never
# recorded or exported itself — it only exists so every step span has
# *something* to parent onto, making them siblings under one shared
# trace_id (a star, not a chain: simpler than threading each step's real
# parent through record_step, and just as valid a trace).
_ROOT_SPAN_ID = 0x0000000000000001

_provider = None


def _tracer_provider():
    global _provider
    if _provider is not None:
        return _provider
    _provider = TracerProvider(
        resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "rag-agent-backend")})
    )
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint:
        # Local import: keeps the OTLP/HTTP + requests dependency chain out
        # of the hot path for the (common, in dev) case where no endpoint
        # is configured at all.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        _provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(_provider)
    return _provider


def _parent_context(trace_id_hex):
    try:
        tid = int(trace_id_hex, 16) if trace_id_hex else 1
    except (TypeError, ValueError):
        tid = 1
    ctx = SpanContext(
        trace_id=tid,
        span_id=_ROOT_SPAN_ID,
        is_remote=True,
        trace_flags=TraceFlags(TraceFlags.SAMPLED),
    )
    return trace.set_span_in_context(NonRecordingSpan(ctx))


def start_step_span(trace_id_hex, name, attributes):
    """Start one span for a RunStep, parented onto the run's shared trace_id.

    Caller (observability.record_step) owns the span's lifetime: set any
    outcome attributes, then call end_step_span().
    """
    tracer = trace.get_tracer("rag-agent", tracer_provider=_tracer_provider())
    span = tracer.start_span(name, context=_parent_context(trace_id_hex))
    for key, value in attributes.items():
        if value is not None:
            span.set_attribute(key, value)
    return span


def end_step_span(span, *, error_type=None):
    if error_type:
        span.set_attribute("error.type", error_type)
        span.set_status(Status(StatusCode.ERROR, error_type))
    span.end()


def span_id_hex(span):
    """The span's own id as 16 lowercase hex chars — the W3C parent-id format."""
    return format(span.get_span_context().span_id, "016x")
