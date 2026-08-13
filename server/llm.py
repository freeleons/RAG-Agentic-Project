import json
import time

import requests
from flask import current_app


class LLMError(Exception):
    """The model endpoint could not be reached or returned an error."""


def _endpoint_and_headers():
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
    {"type": "tool_call", "name": str, "arguments": dict, "call_id": str}."""
    url, headers = _endpoint_and_headers()
    payload = {"model": current_app.config["AGENT_MODEL"], "messages": messages}
    if tools:
        payload["tools"] = tools

    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
            resp.raise_for_status()
            break
        except (requests.exceptions.Timeout, requests.exceptions.RequestException) as exc:
            last_exception = exc
            current_app.logger.warning(
                f"LLM request attempt {attempt}/{max_retries} failed ({type(exc).__name__}). "
                f"Retrying in {attempt * 2}s..."
            )
            if attempt < max_retries:
                time.sleep(attempt * 2)  # Exponential backoff
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
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        call = tool_calls[0]
        raw = call["function"].get("arguments") or "{}"
        try:
            arguments = json.loads(raw)
        except json.JSONDecodeError:
            arguments = {"__parse_error__": raw}
        return {
            "type": "tool_call",
            "name": call["function"]["name"],
            "arguments": arguments,
            "call_id": call.get("id", "call_0"),
            "usage": usage,
        }

    content = message.get("content") or ""
    if "{" in content and "}" in content:
        import re
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                raw_str = match.group(0)
                try:
                    parsed = json.loads(raw_str)
                except Exception:
                    import ast
                    parsed = ast.literal_eval(raw_str)

                if isinstance(parsed, dict):
                    tool_name = (
                        parsed.get("name")
                        or parsed.get("tool")
                        or parsed.get("function")
                    )
                    if tool_name in [
                        "search_knowledge",
                        "list_tickets",
                        "create_ticket",
                        "update_ticket",
                        "delete_ticket",
                        "create_draft",
                        "escalate",
                    ]:
                        args = (
                            parsed.get("arguments")
                            or parsed.get("parameters")
                            or {}
                        )
                        if isinstance(args, str):
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
                pass


    return {"type": "final", "content": content, "usage": usage}

