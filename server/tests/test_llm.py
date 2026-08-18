import pytest
import requests


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _message_payload(message):
    return {"choices": [{"message": message}]}


def test_generate_final_answer(app, monkeypatch):
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["url"] = url
        return FakeResponse(_message_payload({"content": "hi there"}))

    monkeypatch.setattr("server.llm.requests.post", fake_post)
    from server.llm import generate

    result = generate([{"role": "user", "content": "hello"}], [])
    assert result == {
        "type": "final",
        "content": "hi there",
        "usage": {"prompt_tokens": None, "completion_tokens": None},
    }
    assert calls["url"] == "http://localhost:11434/v1/chat/completions"


def test_generate_parses_tool_call(app, monkeypatch):
    payload = _message_payload(
        {
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search_knowledge",
                        "arguments": '{"query": "vpn reset"}',
                    },
                }
            ],
        }
    )
    monkeypatch.setattr("server.llm.requests.post", lambda *a, **k: FakeResponse(payload))
    from server.llm import generate

    result = generate([{"role": "user", "content": "x"}], [])
    assert result == {
        "type": "tool_call",
        "name": "search_knowledge",
        "arguments": {"query": "vpn reset"},
        "call_id": "call_1",
        "usage": {"prompt_tokens": None, "completion_tokens": None},
    }


def test_generate_marks_malformed_arguments(app, monkeypatch):
    payload = _message_payload(
        {
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "escalate", "arguments": "{not json"},
                }
            ]
        }
    )
    monkeypatch.setattr("server.llm.requests.post", lambda *a, **k: FakeResponse(payload))
    from server.llm import generate

    result = generate([], [])
    assert result["arguments"] == {"__parse_error__": "{not json"}


def test_generate_uses_hosted_endpoint_when_configured(app, monkeypatch):
    app.config["AGENT_API_BASE_URL"] = "https://api.example.com/v1"
    app.config["AGENT_API_KEY"] = "sk-test"
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["headers"] = headers
        return FakeResponse(_message_payload({"content": "ok"}))

    monkeypatch.setattr("server.llm.requests.post", fake_post)
    from server.llm import generate

    generate([], [])
    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["headers"]["Authorization"] == "Bearer sk-test"


def test_wait_for_retry_grows_exponentially_with_jitter_cap(monkeypatch):
    """Zero jitter: delays follow LiteLLM exp_backoff = 2 * (base ** n), cap 16s."""
    from server.llm import wait_for_retry

    monkeypatch.setattr("server.llm.random.uniform", lambda a, b: 0)
    # base=2 sequence without jitter: ~2s, ~4s, ~8s (then ~16-24s, here capped)
    assert wait_for_retry(1) == 2.0
    assert wait_for_retry(2) == 4.0
    assert wait_for_retry(3) == 8.0
    assert wait_for_retry(6) == 16.0  # capped at MAX_RETRY_AFTER_SECONDS


def test_wait_for_retry_adds_jitter_in_half_exp_range(monkeypatch):
    """Max jitter is uniform in [0, exp/2] — the thundering-herd spread."""
    from server.llm import wait_for_retry

    monkeypatch.setattr("server.llm.random.uniform", lambda a, b: b)
    # attempt 2: exp=4, jitter=exp/2=2 → 6  (upper end of ~4-6s)
    assert wait_for_retry(2) == 6.0


def test_generate_retries_with_exponential_backoff(app, monkeypatch):
    """Two failures then success: sleeps ~2s then ~4s (jitter mocked to 0)."""
    sleeps = []
    calls = {"n": 0}

    def fake_post(*a, **k):
        calls["n"] += 1
        if calls["n"] < 3:
            raise requests.ConnectionError("refused")
        return FakeResponse(_message_payload({"content": "recovered"}))

    monkeypatch.setattr("server.llm.requests.post", fake_post)
    monkeypatch.setattr("server.llm.random.uniform", lambda a, b: 0)
    monkeypatch.setattr("server.llm.time.sleep", lambda s: sleeps.append(s))
    from server.llm import generate

    result = generate([], [])
    assert result["content"] == "recovered"
    assert sleeps == [2.0, 4.0]


def test_generate_raises_llm_error_on_connection_failure(app, monkeypatch):
    def fake_post(*a, **k):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr("server.llm.requests.post", fake_post)
    monkeypatch.setattr("server.llm.time.sleep", lambda s: None)
    from server.llm import LLMError, generate

    with pytest.raises(LLMError) as caught:
        generate([], [])
    assert caught.value.error_type == "ConnectionError"


def test_generate_timeout_sets_error_type(app, monkeypatch):
    """feat/obs-provider-error-type: Timeout maps to LLMError.error_type.

    中文：超时异常应映射为 error_type == "Timeout"。
    """
    def fake_post(*a, **k):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("server.llm.requests.post", fake_post)
    monkeypatch.setattr("server.llm.time.sleep", lambda s: None)
    from server.llm import LLMError, generate

    with pytest.raises(LLMError) as caught:
        generate([], [])
    assert caught.value.error_type == "Timeout"


def test_llm_provider_ollama_vs_hosted(app):
    """feat/obs-provider-error-type: default ollama; hosted URL → openai_compatible.

    中文：未配置托管 URL 时为 ollama；设置 AGENT_API_BASE_URL 后为 openai_compatible。
    """
    from server.llm import llm_provider

    assert llm_provider() == "ollama"
    app.config["AGENT_API_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai"
    assert llm_provider() == "openai_compatible"


def test_generate_parses_usage(app, monkeypatch):
    payload = {
        "choices": [{"message": {"content": "hi"}}],
        "usage": {"prompt_tokens": 150, "completion_tokens": 20},
    }
    monkeypatch.setattr("server.llm.requests.post", lambda *a, **k: FakeResponse(payload))
    from server.llm import generate

    result = generate([], [])
    assert result["usage"] == {"prompt_tokens": 150, "completion_tokens": 20}
