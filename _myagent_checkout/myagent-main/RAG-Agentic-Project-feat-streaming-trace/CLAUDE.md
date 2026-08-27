# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **starter template** for a 4-week apprentice project: build an AI agent (Flask + React) on top of a running RAG service (AnythingLLM). The Flask agent backend exists under `server/` (models, auth, the agent loop, tools, observability, and HTTP routes, with tests in `server/tests`), and the React frontend exists under `client/` (chat UI and agent-trace panel, plus an Audit tab for run exploration with stats/charts and admin inspection of all users' runs via `ADMIN_EMAILS`), following the spec in `README.md` (the requirements doc / definition of done) and the starter backlog in `docs/seed-issues.md`.

## Architecture

Two systems that talk to each other:

1. **Knowledge service (run, not written)** — AnythingLLM in Docker at `http://localhost:3001`. Documents from `knowledge_base/` are embedded into a workspace; the agent queries it via AnythingLLM's developer API (Bearer key auth, workspace chat endpoint).
2. **The agent (built here)** — Flask backend + React (Vite) frontend. The core is a **bounded agent loop**: the LLM picks a tool → tool executes → LLM observes the result → repeat until done or `MAX_AGENT_STEPS` is hit. One tool is always `search_knowledge(query)` (calls AnythingLLM); at least two more tools per the chosen project option (README §5).

Intended layout (from README):

```
server/
├── app.py
├── agent.py         ← the agent loop (decide → call tool → observe → repeat)
├── tools/           ← one file per tool
├── llm.py           ← generate(messages, tools) — the single model interface
├── observability.py ← decorator logging every LLM/tool call
└── tests/
client/              ← React chat UI + agent-trace panel
```

### Non-negotiable design rules (from the brief)

- **Single model interface:** all model calls go through one `generate(messages, tools)` function (`llm.py`). Default model is Ollama `llama3.1:8b` at `localhost:11434`; swapping to a hosted model must be a config change, not a code change.
- **Single knowledge interface:** all retrieval goes through `search_knowledge(query)` returning `{answer, sources}` — the rest of the agent never touches the AnythingLLM API shape directly.
- **Guardrails:** max-step cap (`MAX_AGENT_STEPS`, default 6), tool-argument validation with exactly one retry then graceful failure, tool timeouts (`TOOL_TIMEOUT_SECONDS`), and **user confirmation before any consequential action** (create/send/escalate).
- **Observability:** every LLM call and tool call is logged (messages, tool, args, latency, result) to a JSON file or DB table, viewable per run.
- **Visible trace:** the UI shows every step (intent, tool, args, result) — this is required, not optional.
- **Prompt-injection awareness:** tool results are clearly delimited; instructions found inside retrieved documents/tool results are never executed.
- Config lives in `.env` (see `.env.example`); never commit a real `.env`.

## Commands

```bash
# Knowledge service (prerequisite — see docs/anythingllm-setup.md)
docker run -d -p 3001:3001 -e STORAGE_DIR="/app/server/storage" \
  -v anythingllm_storage:/app/server/storage \
  --name anythingllm mintplexlabs/anythingllm

# Models (Ollama must be running: `ollama serve`)
ollama pull llama3.1:8b       # agent reasoning model (tool calling)
ollama pull llama3.2:1b       # tiny model for fast local iteration

# Backend (server/)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=agent -e POSTGRES_DB=agentdb \
  -v agentdb_data:/var/lib/postgresql/data --name agentdb postgres:16
python -m venv .venv && source .venv/bin/activate
pip install -r server/requirements.txt
flask --app server.app db upgrade   # create/update the schema
flask --app server.app run --debug  # http://localhost:5000

# Frontend (client/)
npm install
npm run dev                   # http://localhost:5173

# Tests
python -m pytest server/tests -v                                                # all backend tests
python -m pytest server/tests/test_agent.py::test_loop_terminates_at_max_steps -v  # single test
cd client && npm test -- --run                    # frontend tests (single run)
cd client && npm test -- --run src/tests/chat.test.tsx  # single frontend test file
```

Ports: 3001 = AnythingLLM, 5000 = Flask, 5173 = Vite, 5432 = Postgres, 11434 = Ollama.

## Testing conventions

- **Mock the model and tools in tests/CI** — CI must not need a running model or a live AnythingLLM. Assert the agent builds the right tool call, parses results, terminates the loop, and catches malformed tool calls — not that the model says a specific thing.
- Loop termination and stop conditions must have tests.
- CI (GitHub Actions) runs install + lint + tests on every PR; a red build blocks merge.
- The task-based eval set lives in `docs/eval.md` (8–10 goals including 2–3 the agent should decline); re-run it after prompt/tool/model changes and record results there.

## Git workflow (from CONTRIBUTING.md)

- GitHub Flow: short-lived `feature/<name>` branches off protected `main`; all changes via reviewed PRs (≥1 approval), PRs under ~400 lines, linked to issues with `Closes #N`.
- **Conventional Commits** (`feat:`, `fix:`, `chore:`, `docs:`, `test:`, `refactor:`); small focused commits — if the message needs "and," split it.
