"""Central configuration, loaded once from environment variables / .env.

Every tunable of the backend lives here (never hard-coded in application
code), so switching databases, models, or endpoints is a config change only —
one of the non-negotiable design rules in the project brief.
"""

import os

from dotenv import load_dotenv

# Read the project's .env file (if present) into os.environ before we look
# anything up. A real .env is never committed; see .env.example.
load_dotenv()


class Config:
    # Flask session/JWT signing key. The default is intentionally obvious so
    # nobody ships it to production by accident.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")

    # Defaults to a local SQLite file for zero-setup dev; set DATABASE_URL to
    # point at Postgres (postgresql://...) for the full stack.
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///agent.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False  # noisy legacy feature; always off

    # --- Knowledge service (AnythingLLM in Docker) ---------------------------
    # Used by tools/search_knowledge.py and knowledge_sync.py.
    ANYTHINGLLM_BASE_URL = os.environ.get("ANYTHINGLLM_BASE_URL", "http://localhost:3001")
    ANYTHINGLLM_API_KEY = os.environ.get("ANYTHINGLLM_API_KEY", "")
    ANYTHINGLLM_WORKSPACE = os.environ.get("ANYTHINGLLM_WORKSPACE", "apprentice-kb")

    # --- Reasoning model (llm.py) --------------------------------------------
    # By default we talk to a local Ollama server. If AGENT_API_BASE_URL is
    # set, llm.py switches to that hosted OpenAI-compatible endpoint instead —
    # swapping models is a config change, not a code change.
    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    AGENT_MODEL = os.environ.get("AGENT_MODEL", "llama3.1:8b")
    AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "")
    AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "")

    # --- Agent guardrails ----------------------------------------------------
    # Hard cap on loop iterations per run (LLM calls + tool calls combined).
    MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "6"))
    # HTTP timeout for outbound tool calls (e.g. AnythingLLM requests).
    TOOL_TIMEOUT_SECONDS = int(os.environ.get("TOOL_TIMEOUT_SECONDS", "20"))
    JWT_EXPIRY_HOURS = 24

    # Comma-separated list of emails granted admin rights in the Audit tab
    # (admins can see every user's runs). Normalized to a lowercase set.
    ADMIN_EMAILS = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }
