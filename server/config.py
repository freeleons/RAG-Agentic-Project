import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///agent.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ANYTHINGLLM_BASE_URL = os.environ.get("ANYTHINGLLM_BASE_URL", "http://localhost:3001")
    ANYTHINGLLM_API_KEY = os.environ.get("ANYTHINGLLM_API_KEY", "")
    ANYTHINGLLM_WORKSPACE = os.environ.get("ANYTHINGLLM_WORKSPACE", "apprentice-kb")

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    AGENT_MODEL = os.environ.get("AGENT_MODEL", "llama3.1:8b")
    AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "")
    AGENT_API_KEY = os.environ.get("AGENT_API_KEY", "")

    LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY", "")
    LANGSMITH_API_URL = os.environ.get("LANGSMITH_API_URL", "")
    LANGSMITH_PROJECT = os.environ.get("LANGSMITH_PROJECT", "agent-observability")

    MAX_AGENT_STEPS = int(os.environ.get("MAX_AGENT_STEPS", "6"))
    TOOL_TIMEOUT_SECONDS = int(os.environ.get("TOOL_TIMEOUT_SECONDS", "20"))
    JWT_EXPIRY_HOURS = 24

    ADMIN_EMAILS = {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }
