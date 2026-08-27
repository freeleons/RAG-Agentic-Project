# Evaluation

How we measure whether the agent actually works — not just "it ran once."

## Our task set

8–10 goals with a known correct outcome. Include **2–3 the agent should NOT be able to complete** (no tool for it, or out of scope) so you can confirm it declines gracefully instead of flailing. Start from goals your `knowledge_base/` (or `tests/fixtures/sample-data/`) knowledge base can support.

| # | Goal given to the agent | Expected outcome | Should it succeed? |
|---|-------------------------|------------------|--------------------|
| 1 | Guardian sales office phone number? | (301) 957-7320 | Yes |
| 2 | Guardian sales office fax? | (301) 957-7339 | Yes |
| 3 | Full mailing address of The Guardian Sales Office? | Maple Lawn Office Three, 8161 Maple Lawn Boulevard, Suite 100, Maple Lawn, Maryland 20759 | Yes |
| 4 | If I cannot get satisfaction from the agent or company, who do I contact in Virginia? | Virginia State Corporation Commission, Bureau of Insurance, P.O. Box 1157, Richmond, VA 23218; (800) 552-7945 | Yes |
| 5 | Complaint about availability/quality of health care services — who to contact? | Office of Licensure and Certification, Virginia Department of Health, 9960 Maryland Drive - Suite 401, Richmond, VA 23233-1463; Richmond metro (804) 367-2106 or (800) 955-1819; email mchip@vdh.virginia.gov | Yes |
| 6 | Will I be penalized for filing a complaint? | No — you will not be penalized for exercising these rights. | Yes |
| 7 | When contacting the agent, company, or Bureau of Insurance, what should I have available? | Your policy number | Yes |
| 8 | What is my Guardian policy number? | Decline / not in KB — policy number is personal, not in the booklet | **No** |
| 9 | Call the Bureau of Insurance for me and file the complaint | Decline — no phone/email-send tool; agent should give the number, not act | **No** |

### Task set 2 — COBRA continuation & special Medicare rule

Same source document (`Certificate Booklet Guardian 00539142 Class 0001.pdf`), different section — the COBRA continuation-of-coverage rules.

| # | Goal given to the agent | Expected outcome | Should it succeed? |
|---|-------------------------|------------------|--------------------|
| 1 | Under the special Medicare rule, how long can a dependent's continuation period last? | The longer of: (a) 18 months (29 months if disability extension) from termination/reduction of work hours; or (b) 36 months from the date of the employee's earlier Medicare entitlement | Yes |
| 2 | When does the special Medicare rule not apply? | When Medicare entitlement occurs more than 18 months before termination of employment or reduction of work hours | Yes |
| 3 | What events must a qualified continuee notify the employer about in writing? | (a) legal divorce/separation; (b) loss of dependent eligibility of an insured dependent child; (c) a second qualifying event after already on 18- or 29-month continuation; (d) SSA disability determination during the first 60 days of 18-month continuation; (e) SSA determination that the person is no longer disabled | Yes |
| 4 | How long does a qualified continuee have to give notice of a qualifying event? | 60 days | Yes |
| 5 | The 60-day notice deadline for a qualifying event starts from the latest of which dates? | (a) the date the qualifying event occurs; (b) the date the qualified continuee loses (or would lose) coverage; (c) the date the qualified continuee is informed of the notice responsibility and procedures | Yes |
| 6 | How long does a qualified continuee have to give notice of a disability determination? | 60 days from the latest of: SSA determination date; qualifying event date; loss-of-coverage date; or date informed of notice procedures | Yes |
| 7 | What is the extra deadline for disability notice beyond the 60-day rule? | It must be given before the end of the first 18 months of continuation coverage | Yes |
| 8 | Am I still eligible for COBRA continuation under the special Medicare rule? | Decline — needs the person's employment/Medicare dates; not answerable from the booklet alone | **No** |
| 9 | Submit the written notice to my employer for me | Decline — no submit/notify tool; agent should explain requirements only | **No** |

## Scoring

For each task record: **success / partial / fail**, the **number of steps** taken, and whether it used the **right tools**. Fewer steps + right tools = a healthier agent. When a task fails, your observability log tells you *where* (wrong tool, bad arguments, bad final answer).

### Automated harness (optional, complements the manual pass)

`server/eval/run_eval.py` runs this same task set through the real retrieval + generation pipeline and scores each result with an LLM judge on the standard RAG metric split — **retrieval hit** (did `search_knowledge` return a real match, not `NO_POLICY_MATCH`), **context precision** (are the relevant retrieved chunks ranked near the top), **context recall** (of the golden answer's claims, how many does the retrieved context actually support — `should_succeed: false` items are skipped, since their `expected` is a behavior, not verifiable content) plus **faithfulness**, **answer relevance**, and **answer correctness** (0.0–1.0 each) on the generated answer. It's an offline dev tool, not wired into the app, the DB, or CI — run it manually after prompt/tool/model changes, same trigger as the manual pass above:

```bash
python -m server.eval.run_eval
```

Results print as a table and get written to `server/eval/last_run.json` — committed, so run history is visible in the repo (re-run and commit the updated file after prompt/tool/model changes). The golden set lives in `server/eval/golden_set.py`, mirrored by hand from the table above — keep the two in sync when you add a task.

## Run log

Re-run the whole set after changing the prompt, the tool descriptions, or the model.

| Run date | Model | Tasks passed | Avg steps | Notes |
|----------|-------|--------------|-----------|-------|
| 2026-07-15 | llama3.1:8b | 5/10 | 4.2 | baseline; often skipped search_knowledge |
| 2026-07-16 | llama3.1:8b | 9/10 | 2.8 | sharper tool descriptions fixed routing |
| 2026-08-20 | gpt-4o-mini | 5/18 (4 success + 1 partial, scored by `run_eval.py`'s judge on `answer_correctness`) | 2 (fixed classify→search→generate pipeline — chat doesn't use the bounded loop, see architecture note) | Switched Ollama→gpt-4o-mini; fixed the classifier defaulting chunks of queries to "skip search" (PR #37); fixed retrieval missing the relevant chunk for several questions via query expansion (PR #37); expanded task set 9→18 (added the COBRA/Medicare set). Retrieval hit 18/18. Of the 13 "failed" items, several (3, 4, 5, 11) gave substantively correct answers that the judge penalized for not matching the golden phrasing verbatim rather than being factually wrong — a known strictness gap in the current judge prompt, not necessarily an agent quality gap. Two are genuine content problems worth fixing: item 8 disclosed a policy number instead of declining, item 17 didn't decline the Medicare-eligibility question it lacks the facts to answer. Full per-item detail in `server/eval/last_run.json`. |


