# Technical Challenge: Grounded Retrieval vs. Knowing When *Not* to Answer

This is the "one technical challenge and how you solved it" writeup called for in the
presentation deliverable. It's written honestly: part of this challenge is solved,
part of it is a known, currently-open problem — which is itself useful material for
the demo and the Q&A.

## The challenge

The agent has to decide not just *what* the knowledge base says, but *whether it
should answer the question at all*. Two out of the ten "should decline" tasks in our
eval set are ones where retrieval succeeds — the KB genuinely contains relevant text —
but the correct behavior is still to decline, because the question asks for something
personal or individually determined that the document can't establish for the
specific person asking.

That's a harder problem than "did retrieval find something," which is the metric it's
easy to over-optimize for.

## What we started from

Early runs showed the opposite failure mode — the model skipping `search_knowledge`
entirely and guessing:

| Run date | Model | Tasks passed | Notes |
|---|---|---|---|
| 2026-07-15 | llama3.1:8b | 5/10 | baseline; often skipped `search_knowledge` |
| 2026-07-16 | llama3.1:8b | 9/10 | sharper tool descriptions fixed routing |

## What we fixed (PR #37)

Switching to `gpt-4o-mini` and expanding the task set from 9 to 18 goals (adding the
COBRA/Medicare set) surfaced two concrete retrieval bugs, both fixed in PR #37
(`fix/kb-routing-classifier`):

1. The routing classifier ([`PIP_CLASSIFICATION_PROMPT`](../server/prompts.py))
   was defaulting some in-scope queries to "skip search."
2. Retrieval was missing the relevant chunk for several questions — fixed with query
   expansion.

Result: **retrieval hit rate reached 18/18** on the current set
([`docs/eval.md:59`](./eval.md)). The "wrong tool" failure mode is solved.

## What's still open: declining when the context says otherwise

Two items still fail, and both are a *generation*, not *retrieval*, problem —
`retrieval_hit` is `true` for both (data from
[`server/eval/last_run.json`](../server/eval/run_eval.py)):



**Item 17 — "Am I still eligible for COBRA continuation under the special Medicare
rule?"**
The retrieved chunk is general policy language about how the special Medicare rule
works. The agent restates it as if that answers the question, instead of recognizing
that *eligibility* is an individual determination it can't make without the person's
actual employment/Medicare dates. `answer_correctness: 0.0` — *"The answer provides
information not supported by the retrieved context and does not decline as
expected."*

### Root cause

[`PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT`](../server/prompts.py) (server/prompts.py:78-93)
has exactly one decline condition — `NO_POLICY_MATCH`, i.e. retrieval found nothing.
Its Rule 1 ("base your answer strictly on the provided
`AUDITED_POLICY_KNOWLEDGE_RESULT`. Never invent facts") is written to stop
hallucination, but it has a side effect: it never tells the model that *finding*
relevant context isn't the same as the context being *sufficient* to answer this
specific, personal question. There is no rule for "the chunk is real, but doesn't
answer what was actually asked" — so a genuine retrieval hit sails straight through to
an answer.

Worth noting separately: the Pip chat widget's classify → search → generate pipeline
(`server/routes.py`, around `pip_chat()`) doesn't run through the bounded agent loop
in `agent.py` at all — it's a simpler three-step pipeline. The `should_succeed: false`
guardrail behavior we want lives entirely in prompt wording right now, not in a
structural check.

### Why this is worth the demo slot

It's a more interesting story than "we fixed a routing bug": the model isn't failing
because it can't find information — it's failing because *finding related information
feels like license to answer*, even when the question needs facts (who is asking,
what are their dates) that no document can supply. That's a general RAG failure mode,
not an ApexCare-specific one, and it's a good example to have ready for "how do you
know it works / how would you debug it?" in the Q&A — the observability log and the
per-item `reason` field in `last_run.json` are exactly what let us tell items 8 and 17
apart from the judge-strictness false negatives (items 3, 4, 5, 11) instead of lumping
all 13 "failures" together.

### Proposed next step (not yet implemented)

Add an explicit rule to `PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT`: if the retrieved context
doesn't contain facts specific to *this* requester (identity, dates, individual
circumstances) needed to answer the question, decline and say what information would
be needed — even when the context contains adjacent, real policy text. Re-run
`python -m server.eval.run_eval` afterward and confirm items 8 and 17 flip to
`answer_correctness: 1.0` without regressing the 18/18 retrieval-hit rate.

## A second instance of the same failure mode: KB-only instructions crowding out everything else

While fixing a separate bug — `pip_chat()` had no multi-turn memory at all, see
`fix/pip-chat-conversation-context` (PR #40) — manual testing surfaced a live example
of exactly the failure mode described above, outside the eval set.

**Repro:** turn 1, "My name is Dave." Turn 2, "What is my name?" Expected: "Dave."
Actual: *"No matching policy was found in ApexCare documentation for this inquiry.
Please consult HR / IT leadership for guidance."*

This looked at first like the conversation-history fix hadn't worked. It had —
inspecting `RunStep.llm_messages` directly in the database confirmed turn 1's exchange
("my name is Mia" / Pip's reply) was genuinely present in turn 2's call to `generate()`.
The model simply never used it, for a specific, findable reason:

1. `has_knowledge_intent` ([`server/routes.py:1014-1018`](../server/routes.py#L1014-L1018))
   is a keyword regex including `what (is|are)`. "What is my name?" matches it, so the
   turn is routed straight to `SEARCH_KNOWLEDGE` — the same branch item 17 goes through.
2. `search_knowledge` predictably finds nothing about anyone's name, so
   `no_policy_match` is set.
3. `PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT`'s Rule 1 ("base your answer strictly on the
   provided `AUDITED_POLICY_KNOWLEDGE_RESULT`. Never invent facts") applies regardless
   of what else is in `messages` — so the model, correctly following that instruction,
   ignores the conversation history sitting right next to it and outputs the canned
   no-match response.

In other words: passing history into the prompt is necessary but not sufficient. Once a
turn is routed to `SEARCH_KNOWLEDGE`, the system prompt actively tells the model not to
answer from anything *except* the KB result — conversation history included. This is
the same root cause as item 17 (a "must answer only from this narrow source" rule with
no carve-out for "the answer is actually sitting elsewhere in context"), just triggered
by a different, over-broad routing keyword instead of a retrieval hit.

**Proposed fix (not yet implemented, kept out of PR #40's scope on purpose):** narrow
`has_knowledge_intent` so personal/self-referential phrasing ("what is my name",
"what did I just say") doesn't trigger `SEARCH_KNOWLEDGE` on keyword match alone — or,
short of that, add a line to `PIP_SEARCH_KNOWLEDGE_SYSTEM_PROMPT` telling the model to
check conversation history for facts about the requester before falling back to the
no-match template.
