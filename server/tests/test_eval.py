import pytest
from server.eval.run_eval import (
    context_precision,
    context_recall,
    extract_claims,
    get_eval_model_config,
    judge,
    judge_chunk_relevance,
)


def test_context_precision_calculation():
    # Rank 1: rel=1 (1/1=1.0), Rank 2: rel=0, Rank 3: rel=1 (1/3=0.333) -> (1.0 + 0.333) / 2 = 0.667
    assert context_precision([1, 0, 1]) == 0.667
    # Rank 1: rel=1 (1/1=1.0), Rank 2: rel=1 (1/2=0.5) -> (1.0 + 0.5) / 2 = 0.75
    assert context_precision([1, 1, 0]) == 0.75
    # Edge cases
    assert context_precision([]) is None
    assert context_precision(None) is None
    assert context_precision([0, 0, 0]) is None


def test_context_recall_calculation(monkeypatch):
    monkeypatch.setattr(
        "server.eval.run_eval.judge_claim_support",
        lambda claim, context: 1 if "supported" in claim else 0,
    )
    assert context_recall(["claim 1 supported", "claim 2 supported", "claim 3 not"], "context") == 0.667
    assert context_recall([], "context") is None
    assert context_recall(None, "context") is None


def test_extract_claims_handles_markdown_and_json(app, monkeypatch):
    # Tests LLM markdown fence stripping and parsing
    monkeypatch.setattr(
        "server.eval.run_eval.generate",
        lambda messages, tools, model=None, base_url=None, api_key=None: {
            "content": "Here is the list:\n```json\n[\"Phone number is 555-1234\", \"Office is in VA\"]\n```"
        },
    )
    with app.app_context():
        claims = extract_claims("Call 555-1234 in VA")
        assert claims == ["Phone number is 555-1234", "Office is in VA"]


def test_judge_handles_markdown_and_malformed_json(app, monkeypatch):
    monkeypatch.setattr(
        "server.eval.run_eval.generate",
        lambda messages, tools, model=None, base_url=None, api_key=None: {
            "content": "```json\n{\"faithfulness\": 1.0, \"answer_relevance\": 0.9, \"answer_correctness\": 1.0, \"reason\": \"All facts match.\"}\n```"
        },
    )
    with app.app_context():
        res = judge("question", "context", "answer", "expected")
        assert res["faithfulness"] == 1.0
        assert res["answer_relevance"] == 0.9
        assert res["answer_correctness"] == 1.0


def test_judge_error_handling(app, monkeypatch):
    def bad_generate(*args, **kwargs):
        raise ConnectionError("LLM unavailable")

    monkeypatch.setattr("server.eval.run_eval.generate", bad_generate)
    with app.app_context():
        res = judge("q", "c", "a", "e")
        assert res["faithfulness"] is None
        assert "judge error" in res["reason"]


def test_get_eval_model_config(app, monkeypatch):
    monkeypatch.setitem(app.config, "AGENT_MODEL", "gemini-1.5-flash")
    with app.app_context():
        # Default inherits AGENT_MODEL (LLM-agnostic)
        cfg = get_eval_model_config()
        assert cfg["judge_model"] == "gemini-1.5-flash"
        assert cfg["chunk_model"] == "gemini-1.5-flash"

        # Explicit environment overrides
        monkeypatch.setenv("EVAL_JUDGE_MODEL", "gpt-4o-mini")
        monkeypatch.setenv("EVAL_CHUNK_MODEL", "custom-eval-model")
        cfg2 = get_eval_model_config()
        assert cfg2["judge_model"] == "gpt-4o-mini"
        assert cfg2["chunk_model"] == "custom-eval-model"
