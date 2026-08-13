import requests
from flask import current_app


def search_knowledge(query):
    """Query the AnythingLLM workspace. Returns {"answer", "sources"} or {"error"}."""
    cfg = current_app.config
    url = (
        f"{cfg['ANYTHINGLLM_BASE_URL'].rstrip('/')}"
        f"/api/v1/workspace/{cfg['ANYTHINGLLM_WORKSPACE']}/chat"
    )
    
    # Direct AnythingLLM to halt generation immediately if info is missing from document context
    instructed_message = (
        f"{query}\n\n"
        "[Instruction: Search document context strictly. Parse and evaluate all retrieved documents completely first. "
        "Only if the relevant policy information is not explicitly found after checking all available documents, "
        "reply with 'NO_POLICY_MATCH: Information not found in policy documents.' Do not extrapolate or guess.]"
    )

    try:
        resp = requests.post(
            url,
            json={"message": instructed_message, "mode": "query"},
            headers={"Authorization": f"Bearer {cfg['ANYTHINGLLM_API_KEY']}"},
            timeout=cfg["TOOL_TIMEOUT_SECONDS"],
        )
    except requests.RequestException as exc:
        return {"error": f"knowledge service unreachable: {exc}"}
    if resp.status_code in (401, 403):
        return {"error": "knowledge service rejected the API key"}
    if resp.status_code != 200:
        return {"error": f"knowledge service returned HTTP {resp.status_code}"}
    data = resp.json()
    sources = [s.get("title") or s.get("url") or "unknown" for s in data.get("sources", [])]
    return {"answer": data.get("textResponse", ""), "sources": sources}
