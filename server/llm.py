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
import time

import requests
from flask import current_app


class LLMError(Exception):
    """The model endpoint could not be reached or returned an error."""


def _endpoint_and_headers():
    """Pick the chat-completions URL + auth headers from config.

    Hosted endpoint wins if configured; otherwise fall back to local Ollama
    (whose OpenAI-compatible API lives under /v1 and needs no auth).
    """
    cfg = current_app.config
    if cfg.get("AGENT_API_BASE_URL"):
        base = cfg["AGENT_API_BASE_URL"].rstrip("/")
        headers = {"Authorization": f"Bearer {cfg['AGENT_API_KEY']}"}
    else:
        base = cfg["OLLAMA_BASE_URL"].rstrip("/") + "/v1"
        headers = {}
    return f"{base}/chat/completions", headers


def generate(messages, tools, max_retries=3, timeout=120):
    """One model call. Returns {"type": "final", "content": str} or
    {"type": "tool_call", "name": str, "arguments": dict, "call_id": str}.

    Both shapes also carry a "usage" dict (prompt/completion token counts)
    that observability.record_step() strips off and stores on the RunStep.

    `messages` is a standard OpenAI-style list of {"role", "content"} dicts;
    `tools` is the JSON tool schema from tools.openai_tool_defs() (or empty
    for plain chat). Raises LLMError only after all retries are exhausted.
    """
    url, headers = _endpoint_and_headers()
    payload = {"model": current_app.config["AGENT_MODEL"], "messages": messages}
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
            current_app.logger.warning(
                f"LLM request attempt {attempt}/{max_retries} failed ({type(exc).__name__}). "
                f"Retrying in {attempt * 2}s..."
            )
            if attempt < max_retries:
                time.sleep(attempt * 2)  # backoff grows with each attempt: 2s, 4s
    else:
        current_app.logger.error(f"All {max_retries} LLM generation retries exhausted.")
        raise LLMError(f"model call failed after {max_retries} attempts: {last_exception}") from last_exception

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
