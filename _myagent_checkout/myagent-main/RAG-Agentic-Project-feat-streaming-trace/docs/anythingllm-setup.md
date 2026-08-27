# Running the knowledge service (AnythingLLM)

Project 1 is [AnythingLLM](https://github.com/Mintplex-Labs/anything-llm) — a production-grade open-source RAG app. You **run** it; you don't modify it. Your agent (Project 2) calls its API as the `search_knowledge` tool.

## 1. Start it (Docker)

```bash
# STORAGE_DIR is required — without it the container crash-loops on startup.
# It's documented in .env.example; copy that to .env first (cp .env.example .env).
docker run -d -p 3001:3001 \
  -e STORAGE_DIR="/app/server/storage" \
  -v anythingllm_storage:/app/server/storage \
  --name anythingllm mintplexlabs/anythingllm
```

In this GitHub.dev / Codespaces environment, the browser-facing URL is:

https://ideal-space-funicular-jjrqwrvv9g5f95r-3001.app.github.dev/

Use that URL to open the AnythingLLM UI instead of `localhost:3001` when you are accessing it through the forwarded web app. If you are running locally on your own machine, `http://localhost:3001` is still valid; in a forwarded environment, replace it with the public GitHub.dev URL in both the browser and your `.env`.

Open the forwarded URL and complete the first-run setup. (Prefer a desktop app? AnythingLLM also ships one — see their repo. Docker is easiest for a shared, reproducible setup.)

## 2. Point it at a model

In **Settings → LLM Preference**, choose **Ollama** and the model you pulled (e.g. `llama3.1:8b`). This is the model AnythingLLM uses to *answer* from documents — separate from your agent's reasoning model. Make sure `ollama serve` is running.

## 3. Create a workspace and load documents

1. Create a workspace named to match `ANYTHINGLLM_WORKSPACE` in your `.env` (e.g. `apprentice-kb`).
2. Upload the files in [`../knowledge_base/`](../knowledge_base) (or your own corpus) and "Save & Embed" them.
3. Ask a question in the AnythingLLM UI to confirm retrieval works before you wire up the agent.

## 4. Create a developer API key

In **Settings → API Keys**, generate a key and paste it into `.env` as `ANYTHINGLLM_API_KEY`.

## 5. Test the API from the command line

The exact routes are in AnythingLLM's API docs (Settings has a link to the built-in Swagger/API reference). A workspace chat call looks roughly like:

```bash
curl -X POST https://ideal-space-funicular-jjrqwrvv9g5f95r-3001.app.github.dev/api/v1/workspace/apprentice-kb/chat \
  -H "Authorization: Bearer $ANYTHINGLLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "How much does Nimbus Pro cost?", "mode": "query"}'
```

If you are running everything on your own machine, replace the host with `http://localhost:3001`; if you are using GitHub.dev/Codespaces, keep the forwarded URL above. You should get back an answer plus source references. **Check the live API reference for the exact path, request body, and response shape** — wrap whatever you find in your `search_knowledge(query)` function so the rest of your agent doesn't care about the details.

> Treat the response shape as something to *verify*, not assume — read the actual JSON once and build your parser around it.

## 6. Optimize Fast No-Match Fallback

To prevent AnythingLLM from stalling when information is absent from your documents:
1. In **Workspace Settings → Chat Settings → Workspace System Prompt**, configure:
   > *"Given the following context, answer the user query strictly using the provided documents. If the information is not explicitly found in the retrieved documents, reply immediately with 'NO_POLICY_MATCH: Information not found in policy documents.' Do not attempt to guess or hallucinate."*
2. In `search_knowledge.py`, the agent automatically appends a `NO_POLICY_MATCH` instruction to queries, allowing Pip to trigger immediate Tier-2 escalation without delay.
