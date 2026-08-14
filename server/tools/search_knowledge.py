"""The single knowledge interface (a non-negotiable design rule): ALL
retrieval goes through search_knowledge(), which hides the AnythingLLM API
shape from the rest of the codebase. If the knowledge service ever changes,
this file is the only thing that needs editing.
"""

import requests
from flask import current_app


def search_knowledge(query):
    """Query the AnythingLLM workspace. Returns {"answer", "sources"} or {"error"}.

    Uses AnythingLLM's workspace chat endpoint in "query" mode, which runs RAG:
    it embeds the message, retrieves matching chunks from the workspace's
    documents, and has its own model synthesize an answer from them.
    """
    cfg = current_app.config
    url = (
        f"{cfg['ANYTHINGLLM_BASE_URL'].rstrip('/')}"
        f"/api/v1/workspace/{cfg['ANYTHINGLLM_WORKSPACE']}/chat"
    )

    # Direct AnythingLLM to synthesize answers from context but fail gracefully if absent.
    # The exact sentinel string 'NO_POLICY_MATCH' matters: agent prompts and
    # routes.pip_chat() look for it to decide when to escalate instead of answer.
    instructed_message = (
        f"User Query: {query}\n\n"
        "System Instruction: Answer the user's query using ONLY the provided document context. "
        "Review the context carefully to find relevant policy details, guidelines, or procedures. "
        "You may synthesize and summarize the provided text to directly address the query. "
        "If the provided documents do not contain enough relevant information to answer the question, "
        "you must reply exactly with 'NO_POLICY_MATCH: Information not found in policy documents.' "
        "Do not rely on outside knowledge or make assumptions beyond what is written."
    )

    # Failures return {"error": ...} instead of raising: the agent loop treats
    # that as an observation the model can react to (e.g. escalate), and
    # record_step logs it either way.
    try:
        resp = requests.post(
            url,
            json={"message": instructed_message, "mode": "query"},
            headers={"Authorization": f"Bearer {cfg['ANYTHINGLLM_API_KEY']}"},
            timeout=cfg["TOOL_TIMEOUT_SECONDS"],  # tool timeout guardrail
        )
    except requests.RequestException as exc:
        return {"error": f"knowledge service unreachable: {exc}"}

    if resp.status_code in (401, 403):
        return {"error": "knowledge service rejected the API key"}

    if resp.status_code != 200:
        return {"error": f"knowledge service returned HTTP {resp.status_code}"}

    data = resp.json()
    # Flatten the source objects to display names for the trace panel.
    sources = [s.get("title") or s.get("url") or "unknown" for s in data.get("sources", [])]

    return {"answer": data.get("textResponse", ""), "sources": sources}
