def test_record_step_persists_result_and_latency(app, run):
    from server.models import RunStep
    from server.observability import record_step

    result = record_step(
        run.id,
        1,
        "tool_call",
        lambda: {"answer": "42"},
        tool_name="search_knowledge",
        arguments={"query": "meaning"},
    )
    assert result == {"answer": "42"}
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.seq == 1
    assert step.kind == "tool_call"
    assert step.tool_name == "search_knowledge"
    assert step.arguments == {"query": "meaning"}
    assert step.result == {"answer": "42"}
    assert step.latency_ms is not None and step.latency_ms >= 0


def test_record_step_captures_exception_as_error(app, run):
    from server.models import RunStep
    from server.observability import record_step

    def boom():
        raise RuntimeError("model down")

    result = record_step(run.id, 1, "llm_call", boom, llm_messages=[{"role": "user", "content": "x"}])
    assert result == {"error": "model down"}
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.result == {"error": "model down"}
    assert step.error_type == "RuntimeError"
    assert step.llm_messages == [{"role": "user", "content": "x"}]


def test_record_step_classifies_timeout_and_connection_error(app, run):
    """feat/obs-provider-error-type: persist Timeout / ConnectionError on RunStep.

    中文：record_step 应把 Timeout、ConnectionError 写入 RunStep.error_type。
    """
    import requests

    from server.models import RunStep
    from server.observability import record_step

    def timeout():
        raise requests.Timeout("timed out")

    def refused():
        raise requests.ConnectionError("refused")

    record_step(run.id, 1, "llm_call", timeout)
    record_step(run.id, 2, "llm_call", refused)

    steps = RunStep.query.filter_by(run_id=run.id).order_by(RunStep.seq).all()
    assert steps[0].error_type == "Timeout"
    assert steps[1].error_type == "ConnectionError"


def test_record_step_stores_audit_hashes(app, run):
    """feat/audit-log-hardening: arguments/result get an integrity hash
    alongside the plaintext columns.
    """
    from server.models import RunStep
    from server.observability import record_step
    from server.utils import content_hash

    args = {"query": "vpn"}
    record_step(
        run.id,
        1,
        "tool_call",
        lambda: {"answer": "kb says reset"},
        tool_name="search_knowledge",
        arguments=args,
    )
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.arguments_hash == content_hash(args)
    assert step.result_hash == content_hash({"answer": "kb says reset"})


def test_record_step_stores_tokens_and_strips_usage(app, run):
    from server.models import RunStep
    from server.observability import record_step

    result = record_step(
        run.id,
        1,
        "llm_call",
        lambda: {
            "type": "final",
            "content": "hi",
            "usage": {"prompt_tokens": 150, "completion_tokens": 20},
        },
    )
    assert "usage" not in result
    step = RunStep.query.filter_by(run_id=run.id).one()
    assert step.prompt_tokens == 150
    assert step.completion_tokens == 20
    assert "usage" not in step.result
