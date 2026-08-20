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

中文：离线的 RAGAS 风格评测脚本（最小可行版本）。

把 docs/eval.md 里的黄金任务集，跑一遍真实的检索+生成流程（照搬
server/routes.py 里 pip_chat 的 SEARCH_KNOWLEDGE 分支逻辑），然后用一次
judge LLM 调用，按标准 RAG 指标体系给每条结果打分：

  检索质量（Retriever）-> 用 search_knowledge 有没有返回非 NO_POLICY_MATCH
                          的结果来近似（完整的 Context Precision/Recall
                          需要按文本块打标的黄金集，我们现在还没有，这是
                          个粗粒度的替代指标）。
  生成质量（Generator）-> Faithfulness（忠实度）、Answer Relevance（回答
                          相关性）、Answer Correctness（回答正确性），
                          由 judge LLM 打 0.0~1.0 的分。

没有接入线上服务、数据库或 CI，是纯手动跑的开发工具，触发时机跟 docs/eval.md
里那份人工评测一样——改了 prompt/工具/模型之后手动跑一次：

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

# Judge prompt: scores Faithfulness / Answer Relevance / Answer Correctness
# (the Generator-side half of the RAG metric split) against the retrieved
# context and the golden expected outcome.
# 中文：judge 提示词——对着检索到的上下文和黄金期望结果，打 Faithfulness /
# Answer Relevance / Answer Correctness 这三个分（对应 RAG 指标体系里
# Generator 那一侧）。
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

    中文：照搬 routes.py 里 SEARCH_KNOWLEDGE 那条分支的逻辑——先检索，
    再用同样的 system prompt + context 拼装方式生成最终答案，保证评测的
    是真实生产路径，而不是另一套简化逻辑。
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

    中文：调一次 judge LLM，给 faithfulness/answer_relevance/answer_correctness
    打分。如果它没按要求吐纯 JSON（模型偶尔会加解释文字），三项分数都记为
    None 而不是崩掉——None 在打印和 JSON 输出里都会显示成"?"，方便一眼看出
    是"没打到分"而不是被误判成 0.0（真的答错）。
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
    # 中文：这里自建 app + app_context，而不是打真实的 HTTP 接口——这套评测
    # 只关心检索+生成的质量，不关心鉴权/会话那一层，直接调底层函数可以不用
    # 登录 token，也不依赖 Flask/Vite 开发服务器是不是正在跑。
    app = create_app()
    results = []
    with app.app_context():
        for item in GOLDEN_SET:
            kb_result, answer = run_pipeline(item["goal"])
            context = kb_result.get("answer", "") if isinstance(kb_result, dict) else str(kb_result)
            # retrieval_hit is the coarse Retriever-quality proxy described in
            # the module docstring — real Context Precision/Recall would need
            # a chunk-level golden set we don't have.
            # 中文：retrieval_hit 就是模块开头说的那个粗粒度检索质量近似值；
            # 真正的 Context Precision/Recall 需要按文本块打标的黄金集，
            # 现在还没有。
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

    # Human-readable table to stdout for a quick glance...
    # 中文：先打印一张人能一眼看懂的表格……
    print(f"{'#':<3} {'retr':<5} {'faith':<6} {'relev':<6} {'correct':<8} goal")
    for r in results:
        def fmt(v):
            return f"{v:.1f}" if isinstance(v, (int, float)) else "  ?  "
        print(
            f"{r['id']:<3} {'✅' if r['retrieval_hit'] else '❌':<5} "
            f"{fmt(r['faithfulness']):<6} {fmt(r['answer_relevance']):<6} {fmt(r['answer_correctness']):<8} "
            f"{r['goal'][:60]}"
        )

    # ...and the full detail (including retrieved_context, for debugging why
    # a score came out low) to a gitignored JSON file.
    # 中文：……再把完整细节（包括 retrieved_context，方便排查为什么某一项
    # 分低）写进一个 gitignore 掉的 JSON 文件里。
    out_path = "server/eval/last_run.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nFull results written to {out_path}")


if __name__ == "__main__":
    sys.exit(main())
