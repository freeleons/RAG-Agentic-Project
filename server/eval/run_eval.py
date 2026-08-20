"""Offline RAGAS-style eval harness (MVP).

Runs the golden task set in docs/eval.md through the real retrieval +
generation pipeline (mirrors server/routes.py's pip_chat SEARCH_KNOWLEDGE
path) and scores each result with an LLM judge on the standard RAG metric
split:

  Retriever quality  -> retrieval_hit (did search_knowledge return a real
                        match at all) plus context_precision (are the
                        matched chunks ranked with the relevant ones near
                        the top — reciprocal-rank-weighted; each chunk's
                        relevance is judged individually by a local Ollama
                        model, see judge_chunk_relevance).
                        Context Recall is NOT implemented: it needs the
                        golden `expected` answers broken into individual
                        claims to check which ones the retrieved context
                        supports, and we don't have that claim-level data.
  Generator quality  -> Faithfulness, Answer Relevance, Answer Correctness,
                        scored 0.0-1.0 by a judge LLM call.

Not wired into the live app, the DB, or CI. Run manually after prompt/tool/
model changes, same trigger as the manual pass documented in docs/eval.md:

    python -m server.eval.run_eval
"""

import json
import sys

from flask import current_app

from server.app import create_app
from server.eval.golden_set import GOLDEN_SET
from server.llm import generate
from server.prompts import (
    PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT,
    PIP_SYSTEM_PROMPT_NO_POLICY_MATCH,
)
from server.tools.search_knowledge import search_knowledge

# judge call on a free local model instead (see judge_chunk_relevance below).

CHUNK_RELEVANCE_MODEL = "llama3.2:1b"
CHUNK_RELEVANCE_PROMPT = """Does this document excerpt help answer the question? Reply with exactly one word, YES or NO.

QUESTION: {question}

EXCERPT: {excerpt}

Answer (YES or NO only):"""


def judge_chunk_relevance(question, chunk_text):
    """One local-Ollama call: is this single retrieved chunk relevant to the question?

    Deliberately routed to a free, tiny local model (via generate()'s model/
    base_url overrides) instead of the app's configured paid model — this
    runs once per retrieved chunk (up to 4x per golden-set item), and a
    plain yes/no relevance call doesn't need frontier reasoning.
    """
    excerpt = (chunk_text or "")[:800]  # keep the tiny model's prompt short and fast
    prompt = CHUNK_RELEVANCE_PROMPT.format(question=question, excerpt=excerpt)
    ollama_base = current_app.config["OLLAMA_BASE_URL"].rstrip("/") + "/v1"
    res = generate(
        [{"role": "user", "content": prompt}],
        tools=[],
        model=CHUNK_RELEVANCE_MODEL,
        base_url=ollama_base,
    )
    answer = (res.get("content") or "").strip().upper()
    return 1 if answer.startswith("YES") else 0


def context_precision(relevances):
    """Reciprocal-rank-weighted precision over a list of per-chunk relevance labels.

    Context Precision = sum_k(relevance_k * (1 / rank_k)) / total_relevant_chunks

    `relevances` is a 0/1 list in the same order AnythingLLM returned the
    chunks (already sorted highest-similarity first, so index+1 is the rank).
    Returns None when there's nothing to score (no chunks) or nothing
    relevant was found (denominator would be zero) — None prints as "?",
    distinct from a real 0.0.
    """
    if not relevances:
        return None
    total_relevant = sum(relevances)
    if total_relevant == 0:
        return None
    weighted_sum = sum(rel * (1.0 / rank) for rank, rel in enumerate(relevances, start=1))
    return round(weighted_sum / total_relevant, 3)


# Judge prompt: scores Faithfulness / Answer Relevance / Answer Correctness
# (the Generator-side half of the RAG metric split) against the retrieved
# context and the golden expected outcome.
# Note on answer_relevance:  NOT RAGAS's actual formula (generate n
# candidate questions from the answer, embed them, then average the cosine
# similarity against the original question). That needs an embedding model
# and n+1 extra LLM calls per item. This is a cheaper LLM-as-judge stand-in:
# one call, the judge reads the question/answer pair and scores directly.
# Same thing it's meant to catch (off-topic answers, evasive non-answers,
# padded preambles) but the score is a subjective judgment call.
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
    the final answer from the same system prompt + context shape.


    """
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
    """Ask the judge LLM to score faithfulness/relevance/correctness.
    """
    prompt = JUDGE_PROMPT.format(question=question, context=context, answer=answer, expected=expected)
    res = generate([{"role": "user", "content": prompt}], tools=[])
    raw = (res.get("content") or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"faithfulness": None, "answer_relevance": None, "answer_correctness": None, "reason": f"judge output not JSON: {raw[:200]}"}


def main():
    # Build our own app + app_context instead of hitting the live HTTP API:
    # this eval harness cares about retrieval+generation quality, not the
    # auth/session layer, so calling the underlying functions directly
    # avoids needing a login token and a running Flask/Vite dev server.
  
    app = create_app()
    results = []
    with app.app_context():
        for item in GOLDEN_SET:
            kb_result, answer = run_pipeline(item["goal"])
            context = kb_result.get("answer", "") if isinstance(kb_result, dict) else str(kb_result)
            # retrieval_hit: did search_knowledge return a real match at all
            # (coarsest possible Retriever-quality signal).
           
            retrieval_hit = bool(kb_result) and "NO_POLICY_MATCH" not in str(kb_result.get("answer", ""))
            # context_precision: of the chunks that *were* retrieved, are the
            # relevant ones ranked near the top? Judge each chunk individually
            # (local Ollama, cheap) for real relevance labels, then weight by
            # reciprocal rank 
           
            chunks = kb_result.get("chunks", []) if isinstance(kb_result, dict) else []
            relevances = [judge_chunk_relevance(item["goal"], c.get("text")) for c in chunks]
            precision = context_precision(relevances)
            scores = judge(item["goal"], context, answer, item["expected"])
            results.append({
                "id": item["id"],
                "goal": item["goal"],
                "should_succeed": item["should_succeed"],
                "retrieval_hit": retrieval_hit,
                "context_precision": precision,
                "retrieved_context": context,
                "answer": answer,
                **scores,
            })

    # Human-readable table to stdout for a quick glance...
    print(f"{'#':<3} {'retr':<5} {'prec':<6} {'faith':<6} {'relev':<6} {'correct':<8} goal")
    for r in results:
        def fmt(v):
            return f"{v:.2f}" if isinstance(v, (int, float)) else "  ?  "
        print(
            f"{r['id']:<3} {'✅' if r['retrieval_hit'] else '❌':<5} "
            f"{fmt(r['context_precision']):<6} "
            f"{fmt(r['faithfulness']):<6} {fmt(r['answer_relevance']):<6} {fmt(r['answer_correctness']):<8} "
            f"{r['goal'][:60]}"
        )

    # ...and the full detail (including retrieved_context, for debugging why
    # a score came out low) to a JSON file, committed so run history is
    # visible in the repo instead of only existing on whoever's machine ran it.

    out_path = "server/eval/last_run.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
