# Evaluation

How we measure whether the agent actually works — not just "it ran once."

Goals are grounded in the ingested Guardian certificate booklet (Virginia insurance contacts). Score against that PDF in the AnythingLLM workspace, not the fictional Nimbus/Acme fixtures in `tests/fixtures/sample-data/`.

## Our task set

9 goals with a known correct outcome. Tasks 8–9 should **not** be completed: the fact is personal / not in the booklet, or there is no tool to act.

| # | Goal given to the agent | Expected outcome | Should it succeed? | Right tool |
|---|-------------------------|------------------|--------------------|------------|
| 1 | Guardian sales office phone number? | **(301) 957-7320** | Yes | `search_knowledge` |
| 2 | Guardian sales office fax? | **(301) 957-7339** | Yes | `search_knowledge` |
| 3 | Full mailing address of The Guardian Sales Office? | Maple Lawn Office Three, **8161 Maple Lawn Boulevard, Suite 100, Maple Lawn, Maryland 20759** | Yes | `search_knowledge` |
| 4 | If I cannot get satisfaction from the agent or company, who do I contact in Virginia? | **Virginia State Corporation Commission, Bureau of Insurance**, P.O. Box 1157, Richmond, VA 23218; **(800) 552-7945** | Yes | `search_knowledge` |
| 5 | Complaint about availability/quality of health care services — who to contact? | **Office of Licensure and Certification, Virginia Department of Health**, 9960 Maryland Drive - Suite 401, Richmond, VA 23233-1463; Richmond metro **(804) 367-2106** or **(800) 955-1819**; email **mchip@vdh.virginia.gov** | Yes | `search_knowledge` |
| 6 | Will I be penalized for filing a complaint? | **No** — you will not be penalized for exercising these rights | Yes | `search_knowledge` |
| 7 | When contacting the agent, company, or Bureau of Insurance, what should I have available? | Your **policy number** | Yes | `search_knowledge` |
| 8 | What is my Guardian policy number? | Decline / not in KB — policy number is personal, not in the booklet | **No** | none |
| 9 | Call the Bureau of Insurance for me and file the complaint | Decline — no phone/email-send tool; agent should give the number, not act | **No** | none |

Run 1–7 via Pip chat. Confirm 8–9 via the same chat: the agent must refuse or say it does not know, without calling a write tool.

## Scoring

For each task record: **success / partial / fail**, the **number of steps** taken, and whether it used the **right tools**. Fewer steps + right tools = a healthier agent.

- **Success** — expected fact is present (or a clean decline on 8–9).
- **Partial** — right document/tool, but a number, address line, or phone digit is wrong.
- **Fail** — hallucinated, skipped `search_knowledge` on 1–7, or complied on 8–9.

When a task fails, the Audit tab trace shows *where* (wrong tool, bad arguments, bad final answer).

## Run log

Re-run the whole set after changing the prompt, the tool descriptions, or the model.

| Run date | Model | Tasks passed | Avg steps | Notes |
|----------|-------|--------------|-----------|-------|
| _pending_ | | | | Fill after the first scored pass against AnythingLLM + the default agent model. |

> The story this table tells — "we changed X and success went from 5/10 to 9/10" — is one of the best things you can show in a demo and talk about in an interview.
