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
    assert step.llm_messages == [{"role": "user", "content": "x"}]


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


def test_finish_logs_langsmith_run_on_end(app, run, monkeypatch):
    from server.agent import _finish
    from server.langsmith import log_langsmith_run

    called = {}

    def fake_log(run_obj, answer_text):
        called["run_id"] = run_obj.id
        called["answer"] = answer_text

    monkeypatch.setattr("server.agent.log_langsmith_run", fake_log)
    result = _finish(run, "completed", "all done")

    assert result["status"] == "completed"
    assert result["answer"] == "all done"
    assert called["run_id"] == run.id
    assert called["answer"] == "all done"
