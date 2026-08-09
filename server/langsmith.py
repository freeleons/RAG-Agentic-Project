import datetime
import uuid

from flask import current_app

try:
    from langsmith.client import Client
except ImportError:  # pragma: no cover
    Client = None


def _get_client():
    if Client is None:
        return None
    api_key = current_app.config.get("LANGSMITH_API_KEY") or None
    if not api_key:
        return None
    api_url = current_app.config.get("LANGSMITH_API_URL") or None
    return Client(api_key=api_key, api_url=api_url, timeout_ms=120000)


def _serialize_steps(steps):
    serialized = []
    for step in steps:
        item = {
            "seq": step.seq,
            "kind": step.kind,
            "tool_name": step.tool_name,
            "arguments": step.arguments,
            "result": step.result,
            "latency_ms": step.latency_ms,
            "prompt_tokens": step.prompt_tokens,
            "completion_tokens": step.completion_tokens,
        }
        if step.llm_messages is not None:
            item["llm_messages"] = step.llm_messages
        serialized.append(item)
    return serialized


def log_langsmith_run(run, goal):
    client = _get_client()
    if client is None:
        return

    try:
        client.create_run(
            id=str(uuid.uuid4()),
            name=f"agent-run-{run.id}",
            inputs={
                "goal": goal,
                "conversation_id": run.conversation_id,
                "model": run.model,
                "status": run.status,
            },
            outputs={
                "status": run.status,
                "total_latency_ms": run.total_latency_ms,
                "step_count": len(run.steps),
                "trace": _serialize_steps(run.steps),
            },
            run_type="llm",
            project_name=current_app.config.get("LANGSMITH_PROJECT"),
            start_time=run.created_at,
            end_time=datetime.datetime.now(datetime.timezone.utc),
            metadata={
                "run_id": run.id,
                "conversation_id": run.conversation_id,
                "model": run.model,
            },
        )
    except Exception as exc:
        current_app.logger.exception("LangSmith logging failed: %s", exc)
