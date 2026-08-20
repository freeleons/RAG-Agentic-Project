"""Offline RAGAS-style eval harness (MVP).

Runs the golden task set in docs/eval.md through the real retrieval +
generation pipeline (mirrors server/routes.py's pip_chat SEARCH_KNOWLEDGE
path) and scores each result with an LLM judge on the standard RAG metric
split:

  Retriever quality  -> approximated by whether search_knowledge actually
                        returned a non-NO_POLICY_MATCH result (full Context
                        Precision/Recall needs a labeled chunk-level golden
                        set we don't have yet; this is a coarser proxy).
  Generator quality  -> Faithfulness, Answer Relevance, Answer Correctness,
                        scored 0.0-1.0 by a judge LLM call.

Not wired into the live app, the DB, or CI. Run manually after prompt/tool/
model changes, same trigger as the manual pass documented in docs/eval.md:

    python -m server.eval.run_eval
"""

import json
import sys

from server.app import create_app
from server.eval.golden_set import GOLDEN_SET
from server.llm import generate
from server.prompts import (
    PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT,
    PIP_SYSTEM_PROMPT_NO_POLICY_MATCH,
)
from server.tools.search_knowledge import search_knowledge

JUDGE_PROMPT = """You are grading one turn of a RAG support agent. Score three metrics from
0.0 to 1.0 (one decimal place):

- faithfulness: does the ANSWER only state things supported by the RETRIEVED_CONTEXT
  (no invented facts)? An answer that correctly declines when the context has no
  match still scores 1.0 here.
- answer_relevance: does the ANSWER actually address the QUESTION asked (not a
  tangent, not a generic non-answer)?
- answer_correctness: does the ANSWER match the EXPECTED outcome? EXPECTED may
  describe a fact to state verbatim, or a behavior (e.g. "decline, don't invent
  a policy number") — judge against whichever it is.

QUESTION: {question}

RETRIEVED_CONTEXT: {context}

ANSWER: {answer}

EXPECTED: {expected}

Reply with JSON only, no markdown fences:
{{"faithfulness": 0.0, "answer_relevance": 0.0, "answer_correctness": 0.0, "reason": "one short sentence"}}"""


def run_pipeline(goal):
    """Reproduce routes.py's SEARCH_KNOWLEDGE path: retrieve, then generate
    the final answer from the same system prompt + context shape."""
    kb_result = search_knowledge(goal)
    kb_context = ""
    no_policy_match = True
    if kb_result and "error" not in str(kb_result):
        kb_context = f"\n\nAUDITED_POLICY_KNOWLEDGE_RESULT:\n{json.dumps(kb_result)}"
        no_policy_match = "NO_POLICY_MATCH" in str(kb_result.get("answer", ""))

    system_prompt = PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT
    if no_policy_match:
        system_prompt += PIP_SYSTEM_PROMPT_NO_POLICY_MATCH

    messages = [
        {"role": "system", "content": system_prompt + kb_context},
        {"role": "user", "content": goal},
    ]
    res = generate(messages, tools=[])
    answer = res.get("content") or ""
    return kb_result, answer


def judge(question, context, answer, expected):
    prompt = JUDGE_PROMPT.format(question=question, context=context, answer=answer, expected=expected)
    res = generate([{"role": "user", "content": prompt}], tools=[])
    raw = (res.get("content") or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"faithfulness": None, "answer_relevance": None, "answer_correctness": None, "reason": f"judge output not JSON: {raw[:200]}"}


def main():
    app = create_app()
    results = []
    with app.app_context():
        for item in GOLDEN_SET:
            kb_result, answer = run_pipeline(item["goal"])
            context = kb_result.get("answer", "") if isinstance(kb_result, dict) else str(kb_result)
            retrieval_hit = bool(kb_result) and "NO_POLICY_MATCH" not in str(kb_result.get("answer", ""))
            scores = judge(item["goal"], context, answer, item["expected"])
            results.append({
                "id": item["id"],
                "goal": item["goal"],
                "should_succeed": item["should_succeed"],
                "retrieval_hit": retrieval_hit,
                "retrieved_context": context,
                "answer": answer,
                **scores,
            })

    print(f"{'#':<3} {'retr':<5} {'faith':<6} {'relev':<6} {'correct':<8} goal")
    for r in results:
        def fmt(v):
            return f"{v:.1f}" if isinstance(v, (int, float)) else "  ?  "
        print(
            f"{r['id']:<3} {'✅' if r['retrieval_hit'] else '❌':<5} "
            f"{fmt(r['faithfulness']):<6} {fmt(r['answer_relevance']):<6} {fmt(r['answer_correctness']):<8} "
            f"{r['goal'][:60]}"
        )

    out_path = "server/eval/last_run.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
