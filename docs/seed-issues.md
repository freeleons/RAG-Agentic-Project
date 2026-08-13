# Seed issues

Starter backlog so you're not staring at a blank board on Day 2. Copy the ones you need into your team's GitHub Issues, split or merge them to fit your chosen project, and **add your own** — these cover the walking-skeleton path, not the whole project. Refine the acceptance criteria as a team.

> Tip: keep issues small enough to finish in a day or less. If an issue needs the word "and," it's probably two issues.

1. **Run AnythingLLM and load the knowledge base docs**
   - AnythingLLM is reachable at `http://localhost:3001`; a workspace exists with `knowledge_base/` embedded.
   - A developer API key is created and a test query returns an answer via `curl`.

2. **Scaffold the Flask API skeleton**
   - `server/` runs with `flask run` and serves `GET /health` → `{"status":"ok"}`.
   - `requirements.txt` and `.env`-driven config are in place.

3. **Scaffold the React app (Vite)**
   - `client/` runs with `npm run dev` and renders a placeholder chat screen with an empty "trace" panel.
   - It can call `GET /health` and show the result.

4. **Implement the `search_knowledge` tool**
   - A function posts a query to the AnythingLLM workspace API and returns `{answer, sources}`.
   - Errors (bad key, service down) are handled, not crashed. Unit test uses a stubbed HTTP response.

5. **Implement `generate(messages, tools)` behind one interface**
   - One function calls the agent model (Ollama by default) with tool definitions and returns either a tool call or a final answer.
   - Swapping the model is a config change, not a code change.

6. **Build the single-step agent loop**
   - Given a goal, the model selects `search_knowledge`, the tool runs, and the model produces a final answer.
   - The chosen tool + arguments are returned to the frontend.

7. **Add a second and third tool**
   - Two more tools per your project (e.g. `calculator`, `run_sql`, a mock API), each with a clear schema.
   - Each has a unit test with a stubbed implementation.

8. **Make the loop iterate, with a max-step cap**
   - The agent can call multiple tools in sequence until done or `MAX_AGENT_STEPS` is reached.
   - A test proves the loop always terminates.

9. **Argument validation + retry**
   - Tool arguments are validated before execution; one malformed call triggers a single retry, then a graceful failure.

10. **Render the agent trace in the UI**
    - Each step shows intent, tool name, arguments, and result. A user can follow exactly what the agent did.

11. **Add observability logging**
    - A decorator/wrapper logs every model and tool call (messages, tool, args, latency, result) to a JSON file or DB table, with a simple way to view a run.

12. **Authentication + per-user persistence**
    - Signup/login with hashed passwords; conversations and traces are stored per user and survive a restart.

13. **Guardrails: confirmation before consequential actions**
    - Any tool that creates/sends/escalates requires explicit user confirmation in the UI before it runs.

14. **CI (GitHub Actions)**
    - On every PR: install deps, lint, run tests. Model and tool calls are mocked so CI needs no live model or AnythingLLM.
