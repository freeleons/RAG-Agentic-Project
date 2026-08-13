# Evaluation

How we measure whether the agent actually works — not just "it ran once."

## Our task set

8–10 goals with a known correct outcome. Include **2–3 the agent should NOT be able to complete** (no tool for it, or out of scope) so you can confirm it declines gracefully instead of flailing. Start from goals your `knowledge_base/` (or `tests/fixtures/sample-data/`) knowledge base can support.

| # | Goal given to the agent | Expected outcome | Should it succeed? |
|---|-------------------------|------------------|--------------------|
| 1 | _e.g. "What does Nimbus Pro cost, and how many devices on the free plan?"_ | _$8/mo; 3 devices (uses search_knowledge)_ | Yes |
| 2 | | | Yes |
| 3 | | | Yes |
| … | | | |
| n | _e.g. "Delete my account"_ | _declines — no such tool / not permitted_ | **No** |

## Scoring

For each task record: **success / partial / fail**, the **number of steps** taken, and whether it used the **right tools**. Fewer steps + right tools = a healthier agent. When a task fails, your observability log tells you *where* (wrong tool, bad arguments, bad final answer).

## Run log

Re-run the whole set after changing the prompt, the tool descriptions, or the model.

| Run date | Model | Tasks passed | Avg steps | Notes |
|----------|-------|--------------|-----------|-------|
| 2026-07-15 | llama3.1:8b | 5/10 | 4.2 | baseline; often skipped search_knowledge |
| 2026-07-16 | llama3.1:8b | 9/10 | 2.8 | sharper tool descriptions fixed routing |

> The story this table tells — "we changed X and success went from 5/10 to 9/10" — is one of the best things you can show in a demo and talk about in an interview.
