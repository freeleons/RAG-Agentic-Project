---
name: trace-data-flow
description: Trace the execution path of a request or data flow through the repository, ordered by runtime sequence and grounded in actual code. Use this skill when asked to follow what happens from input to output.
---

Use this skill when the user asks to follow a request through the system, explain how data moves from one layer to another, or reconstruct the runtime path from entry point to result.

## Goal
Produce a step-by-step execution trace grounded in repository code, ordered by runtime sequence rather than by directory listing. The answer should clearly show how input enters the system, which code handles it, and where it leaves the repo or reaches an external dependency.

## Process
1. Clarify the entry point for the request or data flow, such as an HTTP route, UI event, tool call, or background job.
2. Locate the first file and function involved using Read, Grep, and Glob.
3. Follow the call chain through handlers, services, models, tool wrappers, and responses.
4. Read the exact code paths for each major step before summarizing them.
5. Present the trace in execution order, from input to output.
6. Identify all relevant external boundaries, including browser interactions, Flask routes, database access, LLM calls, and AnythingLLM/Ollama integrations.

## What to include in the answer
- The starting entry point and the conditions that trigger it.
- Each major step in order, with the file and relevant line ranges.
- The key function or method responsible at each step.
- Inputs, outputs, and state changes between steps.
- Final result, response, persistence, or handoff.

## Output style
Use a numbered trace or short sequence list, for example:
1. `client/src/...` handles user action and prepares request payload.
2. `server/routes.py` receives the request and validates arguments.
3. `server/agent.py` invokes the tool or model loop.
4. `server/tools/...` executes, then returns structured data.
5. The final response is formatted and sent back to the caller.

Cite exact file paths and ranges throughout. If a step crosses a system boundary, call that out explicitly.

## Guardrails
- Do not organize the trace by file alphabetically or folder order.
- Do not skip the handoff points between layers.
- If a request depends on an external service, explain the repo boundary and what payload is sent.
- Stay close to the actual implementation and avoid generic framework explanations.
