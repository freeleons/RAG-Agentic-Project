"""The single model interface: every LLM call in the backend goes through
generate() — one of the non-negotiable design rules.

Both supported backends speak the OpenAI chat-completions wire format:

  - local Ollama (default): POST {OLLAMA_BASE_URL}/v1/chat/completions
  - hosted model:           POST {AGENT_API_BASE_URL}/chat/completions
                            (activated just by setting AGENT_API_BASE_URL)

so swapping models is purely a .env change; no caller ever knows which one
is behind generate().
"""

import json
import random
import time

import requests
from flask import current_app

# Cap wait time so a 429 storm cannot park one request for ~60s.
# before giving up, which inflates P99; we keep max_retries=3 and cap at 16s.
MAX_RETRY_AFTER_SECONDS = 16.0


class LLMError(Exception):
    """The model endpoint could not be reached or returned an error.

    feat/obs-provider-error-type: `error_type` is a stable label for
    observability (Timeout, ConnectionError, HTTPError, …), matching OTel
    error.type more closely than the full message.
    # 中文：`error_type` 是可观测用的稳定标签（Timeout、ConnectionError 等），
    # 比完整错误信息更接近 OTel 的 error.type。
    """

    def __init__(self, message, error_type=None):
        super().__init__(message)
        self.error_type = error_type


def llm_provider():
    """feat/obs-provider-error-type: ollama vs openai_compatible (Gemini, etc.).

    中文：返回当前 LLM 后端——本地 ollama 或托管的 openai_compatible（如 Gemini）。
    """
    if current_app.config.get("AGENT_API_BASE_URL"):
        return "openai_compatible"
    return "ollama"


def stamp_run_llm_identity(run):
    """feat/obs-provider-error-type: copy current model + provider onto the Run.

    中文：把当前 model 和 provider 写入 Run 记录，供审计/可观测使用。
    """
    if not run.model:
        run.model = current_app.config.get("AGENT_MODEL")
    if not run.provider:
        run.provider = llm_provider()


def classify_error_type(exc: BaseException) -> str:
    """feat/obs-provider-error-type: map to Timeout | ConnectionError | type name.

    Check Timeout before ConnectionError because requests.ConnectTimeout
    subclasses both.

    中文：把异常映射为稳定错误类型（Timeout、ConnectionError 或类名）。
    先判断 Timeout 再判断 ConnectionError，因为 ConnectTimeout 同时继承两者。
    """
    named = getattr(exc, "error_type", None)
    if named:
        return named
    if isinstance(exc, requests.Timeout):
        return "Timeout"
    if isinstance(exc, requests.ConnectionError):
        return "ConnectionError"
    cause = getattr(exc, "__cause__", None)
    if cause is not None and cause is not exc:
        return classify_error_type(cause)
    return type(exc).__name__


def wait_for_retry(attempt: int, base: float = 2.0, max_retry_after: float = MAX_RETRY_AFTER_SECONDS) -> float:
    """Seconds to sleep before the next LLM HTTP retry.

    Simplified from litellm/router.py: wait time grows exponentially with jitter
    to avoid a thundering herd (every client retrying at the same instant).

        # exp_backoff = 2 * (base ** attempt), capped at max_retry_after
        # Then add uniform jitter in [0, exp_backoff/2]
        exp = min(2 * (base ** attempt), max_retry_after)
        jitter = random.uniform(0, exp / 2)
        return exp + jitter

    We use `attempt - 1` because generate()'s loop is 1-based (first failure is
    attempt=1). That matches LiteLLM's ~2s, ~4-6s, ~8-12s, ~16-24s sequence
    with base=2, instead of starting at ~4s.
    """
    # exp_backoff = 2 * (base ** (attempt - 1)), capped at max_retry_after
    exp = min(2 * (base ** (attempt - 1)), max_retry_after)
    # Uniform jitter in [0, exp_backoff/2] so concurrent Gemini/Ollama clients
    # do not retry in lockstep after a shared RateLimitError / 429.
    jitter = random.uniform(0, exp / 2)
    return exp + jitter


def _endpoint_and_headers(base_url=None, api_key=None):
    """Pick the chat-completions URL + auth headers from config.

    Hosted endpoint wins if configured; otherwise fall back to local Ollama
    (whose OpenAI-compatible API lives under /v1 and needs no auth).

    `base_url`, when given, skips config entirely and talks to that host.
    If `api_key` is provided (or configured AGENT_API_KEY matches), sets the Bearer auth header.
    """
    if base_url:
        key = api_key or (current_app.config.get("AGENT_API_KEY") if current_app.config.get("AGENT_API_BASE_URL") and current_app.config["AGENT_API_BASE_URL"].rstrip("/") in base_url else None)
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        return f"{base_url.rstrip('/')}/chat/completions", headers
    cfg = current_app.config
    if cfg.get("AGENT_API_BASE_URL"):
        base = cfg["AGENT_API_BASE_URL"].rstrip("/")
        headers = {"Authorization": f"Bearer {cfg['AGENT_API_KEY']}"}
    else:
        base = cfg["OLLAMA_BASE_URL"].rstrip("/") + "/v1"
        headers = {}
    return f"{base}/chat/completions", headers


def generate(messages, tools, max_retries=3, timeout=120, model=None, base_url=None, api_key=None):
    """One model call. Returns {"type": "final", "content": str} or
    {"type": "tool_call", "name": str, "arguments": dict, "call_id": str}.

    Both shapes also carry a "usage" dict (prompt/completion token counts)
    that observability.record_step() strips off and stores on the RunStep.

    `messages` is a standard OpenAI-style list of {"role", "content"} dicts;
    `tools` is the JSON tool schema from tools.openai_tool_defs() (or empty
    for plain chat). Raises LLMError only after all retries are exhausted.

    `model`, `base_url`, and `api_key` are optional overrides for AGENT_MODEL /
    AGENT_API_BASE_URL / AGENT_API_KEY — every production caller (agent.py, routes.py)
    omits them and gets the configured model as before.
    """
    url, headers = _endpoint_and_headers(base_url, api_key)
    payload = {"model": model or current_app.config["AGENT_MODEL"], "messages": messages}
    if tools:
        payload["tools"] = tools

    # --- Retry loop: transient network failures shouldn't kill an agent run.
    # Python quirk: the `else` on a for-loop runs only if we never `break`,
    # i.e. only when every attempt failed.
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            break  # success — leave the retry loop
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as exc:
            last_exception = exc
            err_detail = ""
            if hasattr(exc, "response") and exc.response is not None:
                err_detail = f" [HTTP {exc.response.status_code}: {exc.response.text}]"
            # Hosted Gemini is more likely to 429 than local Ollama; backoff
            # here applies to both backends because they share generate().
            delay = wait_for_retry(attempt) if attempt < max_retries else 0
            current_app.logger.warning(
                f"LLM request attempt {attempt}/{max_retries} failed ({type(exc).__name__}){err_detail}. "
                f"Retrying in {delay:.1f}s..."
            )
            if attempt < max_retries:
                # Attempt sequence with base=2: ~2s, ~4-6s, ~8-12s.
                # Hitting RateLimitErrorRetries: 5 means up to
                # ~60s of waiting; we stop at max_retries=3 plus the 16s cap.
                time.sleep(delay)

    else:
        current_app.logger.error(f"All {max_retries} LLM generation retries exhausted.")
        raise LLMError(
            f"model call failed after {max_retries} attempts: {last_exception}",
            error_type=classify_error_type(last_exception),
        ) from last_exception

    data = resp.json()
    message = data["choices"][0]["message"]
    usage_raw = data.get("usage") or {}
    usage = {
        "prompt_tokens": usage_raw.get("prompt_tokens"),
        "completion_tokens": usage_raw.get("completion_tokens"),
    }

    # --- Case 1: the model used native tool calling -------------------------
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        # The agent loop executes exactly one tool per step, so we only take
        # the first call even if the model emitted several.
        call = tool_calls[0]
        raw = call["function"].get("arguments") or "{}"
        try:
            arguments = json.loads(raw)
        except json.JSONDecodeError:
            # Don't crash on malformed JSON — hand the raw string to
            # validate_arguments(), which will reject it and trigger the
            # agent's one-retry-then-fail guardrail.
            arguments = {"__parse_error__": raw}
        return {
            "type": "tool_call",
            "name": call["function"]["name"],
            "arguments": arguments,
            "call_id": call.get("id", "call_0"),
            "usage": usage,
        }

    # --- Case 2: fallback tool-call detection in plain text ------------------
    # Small local models (llama3.1:8b) sometimes ignore native tool calling and
    # instead print JSON like {"name": "search_knowledge", "arguments": {...}}
    # directly in their answer. If the reply contains a JSON object naming one
    # of our known tools, treat it as a tool call rather than a final answer.
    content = message.get("content") or ""
    if "{" in content and "}" in content:
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)  # widest {...} span
        if match:
            try:
                raw_str = match.group(0)
                try:
                    parsed = json.loads(raw_str)
                except Exception:
                    # Models sometimes emit Python-style dicts (single quotes);
                    # ast.literal_eval handles those safely.
                    import ast
                    parsed = ast.literal_eval(raw_str)

                if isinstance(parsed, dict):
                    # Accept the common key spellings models use for the tool name.
                    tool_name = (
                        parsed.get("name")
                        or parsed.get("tool")
                        or parsed.get("function")
                    )
                    if tool_name in [
                        "search_knowledge",
                        "list_tickets",
                        "update_ticket",
                        "escalate",
                    ]:
                        args = (
                            parsed.get("arguments")
                            or parsed.get("parameters")
                            or {}
                        )
                        if isinstance(args, str):
                            # Arguments given as a nested JSON string, or as a
                            # bare query string — normalize either way.
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"query": args}
                        return {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": args if isinstance(args, dict) else {},
                            "call_id": "call_fallback",
                            "usage": usage,
                        }
            except Exception:
                # Any parsing hiccup here just means "not a tool call" —
                # fall through and return the text as a final answer.
                pass

    # --- Case 3: a plain final answer ----------------------------------------
    return {"type": "final", "content": content, "usage": usage}
