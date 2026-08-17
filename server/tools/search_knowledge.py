import re
import requests
from flask import current_app


def expand_knowledge_query(query: str) -> str:
    """Expand abbreviations and policy synonyms to maximize vector retrieval recall."""
    if not query or not isinstance(query, str):
        return ""
    q = query.strip()

    EXPANSIONS = [
        (r"\b(wfa|work from anywhere|remote work|remote|telework|wfh|home office stipend)\b", "Work From Anywhere (WFA) & Remote Work Policy home office stipend travel allowance"),
        (r"\b(wex|mobile app|claim submission|reimbursement|receipt|file a claim|upload documentation)\b", "WEX Benefits Technology & Resources mobile app participant portal file a claim upload documentation phone camera barcode scan wexinc.com 1-866-451-3399 customerservice@wexhealth.com forms@wexhealth.com"),
        (r"\b(fsa|flexible spending|rollover limit|dependent care)\b", "Flexible Spending Accounts (FSA) Financial Limits WEX Healthcare FSA rollover $640 $3,200"),
        (r"\b(pto|paid time off|vacation|holidays?|floating holiday)\b", "Paid Time Off (PTO) & Company Holidays accrual rollover 40 hours floating holidays"),
        (r"\b(parental leave|maternity|paternity|primary caregiver|secondary caregiver)\b", "Paid Parental Leave Primary Caregiver 16 weeks Secondary Caregiver 8 weeks"),
        (r"\b(401k|401\(k\)|retirement|match|vesting)\b", "401(k) Retirement Plan & Employer Match formula 100% 4% 50% vesting auto-enrollment"),
        (r"\b(bereavement|funeral|loss of family)\b", "Bereavement Leave Immediate Family 5 days Extended Family 3 days travel extension"),
        (r"\b(tuition|reimbursement|degree|certifications?|professional development)\b", "Tuition Reimbursement & Professional Development $5,250 $1,500 budget clawback"),
        (r"\b(qle|qualifying life event|life event|navigator)\b", "Qualifying Life Events QLE Employee Navigator Instructions enrollment 30 days"),
        (r"\b(std|short term disability|disability income|elimination period)\b", "Voluntary Short-Term Disability (STD) income coverage 60% maximum $1,800/week elimination period Day 8 26 weeks Vol STD 2026"),
        (r"\b(dental|vision|guardian|out of network|out-of-network|group number|00539142)\b", "Guardian Group Benefits Certificate Booklet 00539142 Class 0001 Dental Expense Insurance Vision Care Deductibles $50 $0 out-of-network claim reimbursement PO Box 981573 El Paso TX 79998-1573"),
        (r"\b(id card|medical card|insurance card|temporary card|print id card|myuhc)\b", "myuhc.com How to print a temporary medical ID Card UnitedHealthcare digital engagement flier"),
    ]

    matched_topics = []
    for pattern, expansion in EXPANSIONS:
        if re.search(pattern, q, re.IGNORECASE):
            matched_topics.append(expansion)

    if matched_topics:
        return f"{q} ({' | '.join(matched_topics)})"
    return q


def extract_core_search_query(query: str) -> str:
    """Extract the actual policy question from ticket wrapper text or draft requests."""
    if not query or not isinstance(query, str):
        return ""
    q = query.strip()
    m = re.search(r'\"([^\"]+)\"', q)
    if m:
        extracted = m.group(1).strip()
        extracted = re.sub(r"^(hi|hello)\s+(hr\s*team|hr|team|all)[,\.\!]?\s*", "", extracted, flags=re.IGNORECASE).strip()
        if len(extracted) > 10:
            return extracted
    cleaned = re.sub(
        r"^(help me (write a draft reply|draft a reply|answer)|draft a reply to|can you tell me)\s+(to\s+[^:]+:\s*)?",
        "",
        q,
        flags=re.IGNORECASE,
    ).strip()
    return cleaned


def search_knowledge(query):
    """Query the AnythingLLM workspace with expanded query. Returns {"answer", "sources"} or {"error"}.

    Uses AnythingLLM's workspace chat endpoint in "query" mode, which runs RAG:
    it embeds the message, retrieves matching chunks from the workspace's
    documents, and has its own model synthesize an answer from them.
    """
    cfg = current_app.config
    url = (
        f"{cfg['ANYTHINGLLM_BASE_URL'].rstrip('/')}"
        f"/api/v1/workspace/{cfg['ANYTHINGLLM_WORKSPACE']}/chat"
    )

    core_query = extract_core_search_query(query)
    expanded_query = expand_knowledge_query(core_query if core_query else query)

    # Direct AnythingLLM to synthesize answers from context but fail gracefully if absent.
    instructed_message = (
        f"Inquiry: {expanded_query}\n\n"
        "System Instruction: Answer the inquiry strictly using the provided document context. "
        "Extract and summarize the relevant policy rules, numbers, limits, percentages, and guidelines. "
        "If the provided documents do not contain relevant information to address the inquiry, "
        "reply with 'NO_POLICY_MATCH: Information not found in policy documents.' "
        "Do not rely on outside knowledge."
    )

    # Failures return {"error": ...} instead of raising: the agent loop treats
    # that as an observation the model can react to (e.g. escalate), and
    # record_step logs it either way.
    timeout_val = max(int(cfg.get("TOOL_TIMEOUT_SECONDS", 180)), 180)
    try:
        resp = requests.post(
            url,
            json={"message": instructed_message, "mode": "query"},
            headers={"Authorization": f"Bearer {cfg['ANYTHINGLLM_API_KEY']}"},
            timeout=timeout_val,  # tool timeout guardrail (minimum 180s for local LLMs)
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
