"""feat/otel-tracing: record_step() emits one real OTel span per RunStep,
all sharing the Run's W3C trace_id.

Spans are captured with an in-memory exporter (swapped into tracing._provider
directly) instead of asserting against a live OTLP backend — record_step()
never talks to the network on its own; only OTEL_EXPORTER_OTLP_ENDPOINT
being set does that (see tracing._tracer_provider).
"""

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

import server.tracing as tracing


@pytest.fixture
def span_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracing._provider = provider
    yield exporter
    tracing._provider = None


def test_run_gets_a_real_trace_id(run):
    assert run.trace_id is not None
    assert len(run.trace_id) == 32
    int(run.trace_id, 16)  # valid hex


def test_llm_call_step_span_shares_run_trace_id_and_has_gen_ai_attrs(app, run, span_exporter):
    from server.observability import record_step

    record_step(
        run.id,
        1,
        "llm_call",
        lambda: {"type": "final", "content": "hi"},
        llm_messages=[{"role": "user", "content": "hi"}],
    )
    spans = span_exporter.get_finished_spans()
    assert len(spans) == 1
    span = spans[0]
    assert format(span.context.trace_id, "032x") == run.trace_id
    assert span.attributes["gen_ai.operation.name"] == "chat"
    assert span.attributes["gen_ai.request.model"] == run.model


def test_tool_call_step_span_has_tool_name_attribute(app, run, span_exporter):
    from server.observability import record_step

    record_step(
        run.id,
        1,
        "tool_call",
        lambda: {"answer": "42"},
        tool_name="search_knowledge",
        arguments={"query": "x"},
    )
    span = span_exporter.get_finished_spans()[0]
    assert span.attributes["gen_ai.operation.name"] == "execute_tool"
    assert span.attributes["gen_ai.tool.name"] == "search_knowledge"


def test_two_steps_in_one_run_share_trace_id(app, run, span_exporter):
    from server.observability import record_step

    record_step(run.id, 1, "llm_call", lambda: {"type": "final", "content": "a"})
    record_step(run.id, 2, "tool_call", lambda: {"ok": True}, tool_name="t", arguments={})
    spans = span_exporter.get_finished_spans()
    trace_ids = {format(s.context.trace_id, "032x") for s in spans}
    assert trace_ids == {run.trace_id}
    # Distinct span ids, both persisted on their RunStep rows.
    from server.models import RunStep

    steps = RunStep.query.filter_by(run_id=run.id).order_by(RunStep.seq).all()
    span_ids = {s.span_id for s in steps}
    assert len(span_ids) == 2
    assert all(sid and len(sid) == 16 for sid in span_ids)


def test_failed_step_marks_span_error(app, run, span_exporter):
    from server.observability import record_step

    def boom():
        raise RuntimeError("model down")

    record_step(run.id, 1, "llm_call", boom)
    span = span_exporter.get_finished_spans()[0]
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["error.type"] == "RuntimeError"


def test_run_step_span_id_matches_emitted_span(app, run, span_exporter):
    from server.models import RunStep
    from server.observability import record_step

    record_step(run.id, 1, "tool_call", lambda: {"ok": True}, tool_name="t", arguments={})
    span = span_exporter.get_finished_spans()[0]
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.span_id == format(span.context.span_id, "016x")
