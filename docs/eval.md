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

## Scoring

For each task record: **success / partial / fail**, the **number of steps** taken, and whether it used the **right tools**. Fewer steps + right tools = a healthier agent. When a task fails, your observability log tells you *where* (wrong tool, bad arguments, bad final answer).

### Automated harness (optional, complements the manual pass)

`server/eval/run_eval.py` runs this same task set through the real retrieval + generation pipeline and scores each result with an LLM judge on the standard RAG metric split — **retrieval hit** (did `search_knowledge` return a real match, not `NO_POLICY_MATCH`) plus **faithfulness**, **answer relevance**, and **answer correctness** (0.0–1.0 each) on the generated answer. It's an offline dev tool, not wired into the app, the DB, or CI — run it manually after prompt/tool/model changes, same trigger as the manual pass above:

```bash
python -m server.eval.run_eval
```

Results print as a table and get written to `server/eval/last_run.json` (gitignored — regenerate, don't commit). The golden set lives in `server/eval/golden_set.py`, mirrored by hand from the table above — keep the two in sync when you add a task.

## Run log

Re-run the whole set after changing the prompt, the tool descriptions, or the model.

| Run date | Model | Tasks passed | Avg steps | Notes |
|----------|-------|--------------|-----------|-------|
| 2026-07-15 | llama3.1:8b | 5/10 | 4.2 | baseline; often skipped search_knowledge |
| 2026-07-16 | llama3.1:8b | 9/10 | 2.8 | sharper tool descriptions fixed routing |

> The story this table tells — "we changed X and success went from 5/10 to 9/10" — is one of the best things you can show in a demo and talk about in an interview.
