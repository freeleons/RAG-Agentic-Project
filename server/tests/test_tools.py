import requests


def test_openai_tool_defs_shape(app):
    from server.tools import openai_tool_defs

    defs = openai_tool_defs()
    names = [d["function"]["name"] for d in defs]
    assert "search_knowledge" in names
    for d in defs:
        assert d["type"] == "function"
        assert "parameters" in d["function"]


def test_validate_arguments(app):
    from server.tools import validate_arguments

    assert validate_arguments("no_such_tool", {}) is not None
    assert validate_arguments("search_knowledge", "not a dict") is not None
    assert validate_arguments("search_knowledge", {}) is not None  # missing query
    assert validate_arguments("search_knowledge", {"query": ""}) is not None  # empty
    assert validate_arguments("search_knowledge", {"query": 42}) is not None  # wrong type
    assert (
        validate_arguments("search_knowledge", {"query": "x", "bogus": 1}) is not None
    )  # unknown key
    assert validate_arguments("search_knowledge", {"query": "vpn"}) is None


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def test_search_knowledge_parses_answer_and_sources(app, monkeypatch):
    monkeypatch.setitem(app.config, "ANYTHINGLLM_WORKSPACE", "apprentice-kb")
    payload = {
        "textResponse": "Nimbus Pro costs $8/mo.",
        "sources": [
            {"title": "nimbus-faq.txt", "score": 0.61, "text": "Nimbus Pro is $8/mo per seat."},
            {"url": "http://kb/doc2", "score": 0.44, "text": "Nimbus Pro includes 10GB storage."},
        ],
    }
    seen = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        seen["url"] = url
        seen["auth"] = headers["Authorization"]
        return FakeResponse(payload)

    monkeypatch.setattr("server.tools.search_knowledge.requests.post", fake_post)
    from server.tools.search_knowledge import search_knowledge

    result = search_knowledge("nimbus price")
    assert result == {
        "answer": "Nimbus Pro costs $8/mo.",
        "sources": ["nimbus-faq.txt", "http://kb/doc2"],
        "chunks": [
            {"title": "nimbus-faq.txt", "score": 0.61, "text": "Nimbus Pro is $8/mo per seat."},
            {"title": "http://kb/doc2", "score": 0.44, "text": "Nimbus Pro includes 10GB storage."},
        ],
    }
    assert seen["url"] == "http://localhost:3001/api/v1/workspace/apprentice-kb/chat"
    assert seen["auth"].startswith("Bearer ")


def test_search_knowledge_handles_bad_key(app, monkeypatch):
    monkeypatch.setattr(
        "server.tools.search_knowledge.requests.post",
        lambda *a, **k: FakeResponse({}, status=403),
    )
    from server.tools.search_knowledge import search_knowledge

    assert "error" in search_knowledge("x")


def test_search_knowledge_handles_timeout(app, monkeypatch):
    def fake_post(*a, **k):
        raise requests.Timeout("too slow")

    monkeypatch.setattr("server.tools.search_knowledge.requests.post", fake_post)
    from server.tools.search_knowledge import search_knowledge

    assert "error" in search_knowledge("x")
