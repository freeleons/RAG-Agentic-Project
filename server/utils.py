import json
import re
from flask import request


def clean_draft_text(raw_text: str) -> str:
    """Extract clean human-readable draft text if the LLM outputted raw JSON or tool-call schema."""
    if not raw_text or not isinstance(raw_text, str):
        return ""
    text = raw_text.strip()

    # 1. Check if enclosed in markdown code fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    # 2. Try JSON parsing directly or searching for embedded JSON object
    json_candidate = None
    if text.startswith("{") and text.endswith("}"):
        try:
            json_candidate = json.loads(text)
        except Exception:
            pass

    if not json_candidate:
        json_match = re.search(r"(\{[\s\S]*\})", text)
        if json_match:
            try:
                json_candidate = json.loads(json_match.group(1))
            except Exception:
                pass

    if isinstance(json_candidate, dict):
        body = None
        params = json_candidate.get("parameters")
        if isinstance(params, dict):
            reply_obj = params.get("reply")
            if isinstance(reply_obj, dict) and "body" in reply_obj:
                body = reply_obj["body"]
            elif isinstance(reply_obj, str):
                body = reply_obj
            elif "body" in params and isinstance(params["body"], str):
                body = params["body"]

        if not body:
            reply_obj = json_candidate.get("reply")
            if isinstance(reply_obj, dict) and "body" in reply_obj:
                body = reply_obj["body"]
            elif isinstance(reply_obj, str):
                body = reply_obj
            elif "body" in json_candidate and isinstance(json_candidate["body"], str):
                body = json_candidate["body"]
            elif "draft_reply" in json_candidate and isinstance(json_candidate["draft_reply"], str):
                body = json_candidate["draft_reply"]
            elif "draft" in json_candidate and isinstance(json_candidate["draft"], str):
                body = json_candidate["draft"]

        if body and isinstance(body, str):
            text = body.strip()
        else:
            # It was a JSON object that did NOT contain a draft email body
            return ""

    # 3. Strip any preamble phrases like "I have inserted this response in the reply chat:"
    preamble_patterns = [
        r"^I have inserted this (response|draft) (in|into) the (reply chat|reply box|ticket reply):\s*",
        r"^Here is the (draft|response|reply)( for the employee)?:\s*",
        r"^I have drafted a response( below)?:\s*",
    ]
    for pat in preamble_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip()

    # 4. Clean up any leftover escaped newlines if unparsed
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")

    # 5. Strip surrounding quotes / whitespace
    text = text.strip(" \t\r\n\"'“”`")

    # If stripped quotes revealed another preamble, strip again
    for pat in preamble_patterns:
        text = re.sub(pat, "", text, flags=re.IGNORECASE).strip(" \t\r\n\"'“”`")

    return text


def format_knowledge_answer(raw_answer: str, sources: list = None) -> str:
    """Pre-render and clean knowledge search queries into natural, friendly markdown."""
    if not raw_answer:
        return ""
    ans = str(raw_answer).strip()

    # 1. Strip prompt leakage / echo of injected context
    ans = re.sub(r"\n*CURRENT_ACTIVE_TICKETS:[\s\S]*", "", ans).strip()
    ans = re.sub(r"\n*AUDITED_POLICY_KNOWLEDGE_RESULT:[\s\S]*", "", ans).strip()
    ans = re.sub(r"\n*\[SYSTEM STATUS: NO_POLICY_MATCH\][\s\S]*", "", ans).strip()

    # 2. Check for NO_POLICY_MATCH sentinel
    if "NO_POLICY_MATCH" in ans:
        ans = (
            "**No matching policy was found in ApexCare documentation for this inquiry.**\n\n"
            "Please consult HR / IT leadership directly for guidance on company policies and benefits."
        )
        return ans

    # 3. Strip raw RAG context tags like According to [CONTEXT 1]: "..." -> bold topic
    ans = re.sub(r'According to \[CONTEXT \d+\]:\s*"?([^",\n]+)"?,?\s*', r'**\1**:\n', ans)
    ans = re.sub(r'\[CONTEXT \d+\]:?\s*', '', ans)
    ans = ans.strip()

    # 4. Append unique formatted source citations if provided
    if sources and isinstance(sources, list):
        clean_sources = []
        seen = set()
        for src in sources:
            if not src or not isinstance(src, str):
                continue
            name = src.strip().replace(".pdf", "").replace(".md", "").replace("_", " ").replace("-", " ")
            name = " ".join([w.capitalize() for w in name.split()])
            if name and name.lower() not in seen:
                seen.add(name.lower())
                clean_sources.append(name)
        if clean_sources and "📄 **Sources:**" not in ans and "**Source" not in ans:
            src_str = ", ".join(clean_sources)
            ans = f"{ans}\n\n📄 **Sources:** {src_str}"

    return ans


def is_client_disconnected():
    """Check if the HTTP client has closed/aborted the connection.

    Agent runs can take many seconds; the loop polls this between steps so a
    closed browser tab stops the run instead of burning model calls nobody
    will see.

    Implementation note: this reaches into private attributes of Werkzeug's
    dev-server socket, so it is best-effort only — on any other WSGI server
    (gunicorn, tests) the attribute chain fails and we conservatively report
    "still connected" (False). The Stop button (run.status='stopped' in the
    DB) is the reliable cancellation path; this is just an optimization.
    """
    try:
        # Accessing the underlying WSGI socket environment to test connection state
        environ = request.environ
        # Check for socket closing signals or closed stream
        return environ.get("wsgi.input").get_socket()._closed
    except Exception:
        return False
