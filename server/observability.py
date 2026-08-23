"""Observability: the one choke point through which every LLM call and tool
call is executed AND logged. The agent loop never calls generate() or a tool
handler directly — it always goes through record_step(), which guarantees the
trace in the run_steps table is complete.

feat/obs-provider-error-type: one RunStep per LLM/tool call (one inference
span). Run.id is the trace; RunStep.seq is span order. We store
gen_ai.provider.name on Run and error.type on failed steps.

"""

import time

from server.llm import classify_error_type
from server.models import RunStep, db
from server.utils import content_hash


def record_step(run_id, seq, kind, fn, *, tool_name=None, arguments=None, llm_messages=None):
    """Execute fn(), timing it, and persist the outcome as a RunStep.

    Never raises: an exception from fn() is captured as {"error": ...} so the
    agent loop can degrade gracefully while the failure stays in the log.
    """
    start = time.perf_counter()
    error_type = None
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 — every failure must reach the log
        result = {"error": str(exc)}
        error_type = classify_error_type(exc)
    latency_ms = int((time.perf_counter() - start) * 1000)
    # generate() piggybacks token usage on its result; pull it out so it lands
    # in dedicated columns instead of being duplicated inside `result`.
    usage = {}
    if isinstance(result, dict) and "usage" in result:
        usage = result.pop("usage") or {}
    # The result column is JSON; wrap non-dict values so storage is uniform.
    stored = result if isinstance(result, dict) else {"value": result}
    # Audit fingerprints, computed from exactly what gets stored in the
    # plaintext columns below (post usage-extraction) so a later re-hash of
    # `arguments`/`result` always matches.
    step = RunStep(
        run_id=run_id,
        seq=seq,
        kind=kind,
        tool_name=tool_name,
        arguments=arguments,
        result=stored,
        llm_messages=llm_messages,
        latency_ms=latency_ms,
        prompt_tokens=usage.get("prompt_tokens"),
        completion_tokens=usage.get("completion_tokens"),
        error_type=error_type,
        arguments_hash=content_hash(arguments),
        result_hash=content_hash(stored),
    )
    db.session.add(step)
    db.session.commit()
    return result
