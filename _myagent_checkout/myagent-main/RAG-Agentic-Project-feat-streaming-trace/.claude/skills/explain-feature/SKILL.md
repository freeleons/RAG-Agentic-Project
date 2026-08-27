---
name: explain-feature
description: Use this skill to explain how a specific feature or workflow works in this repository, citing exact file paths and line numbers. Focus on concrete implementation details instead of generic architecture.
---

Use this skill when the user asks how a feature works, why a workflow behaves a certain way, or where a behavior is implemented in the codebase.

## Goal
Explain a repository feature in concrete, implementation-level terms. The response should answer: what the feature is, where it is implemented, how it works at runtime, and which files or functions are involved.

## Process
1. Confirm the user's feature request and identify the relevant area: server, client, docs, or tests.
2. Use Read, Grep, and Glob to locate the implementation and the nearest supporting files.
3. Read the exact files and line ranges that define the behavior, not just the file names.
4. Trace the main execution path from input to result, including validation, state changes, API calls, and UI updates.
5. Summarize the feature with precise file paths and line numbers.
6. Note external boundaries such as the browser, Flask routes, AnythingLLM, Ollama, Postgres, or any third-party service.

## What to include in the answer
- A short plain-language explanation of the feature or workflow.
- The key files and symbols involved, with exact citations.
- The runtime flow in a few steps, starting from the entry point.
- Important guardrails, state transitions, or conditions that affect behavior.
- Where the repo hands off to external systems or infrastructure.

## Output style
Keep the explanation grounded in the code. Prefer direct references like:
- `server/routes.py:42-68`
- `server/agent.py:120-210`
- `client/src/chat/ChatView.tsx:56-125`

Avoid vague descriptions like “it probably does X” or architecture summaries that do not reference the code. If a detail is uncertain, say that the repository does not show it explicitly and explain the boundary.

## Guardrails
- Do not invent missing behavior.
- Prefer exact file evidence over assumptions.
- Focus on the feature being asked about, not the entire system.
- Keep the answer specific and actionable for future debugging or code review.
