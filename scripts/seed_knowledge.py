#!/usr/bin/env python3
"""
Seed knowledge base documents to AnythingLLM.

This script:
1. Scans knowledge_base/ directory for audited .md and .txt files.
2. Reads existing workspace documents from AnythingLLM to avoid duplicates.
3. Uploads new files to AnythingLLM and embeds them into the workspace in a single call.
4. Logs execution status and summary.

Usage:
    python -m scripts.seed_knowledge
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from server.config import Config

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class AnythingLLMClient:
    """Client for AnythingLLM REST API endpoints."""

    def __init__(self, base_url: str, api_key: str, workspace_slug: str):
        self.api_base = base_url.rstrip("/") + "/api"
        self.workspace_slug = workspace_slug
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def get_workspace_documents(self) -> List[Dict[str, Any]]:
        """Fetch current documents in the workspace from GET /v1/workspace/{slug}."""
        url = f"{self.api_base}/v1/workspace/{self.workspace_slug}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.raise_for_status()
            workspaces = resp.json().get("workspace") or []
            if not workspaces:
                logger.warning(f"Workspace '{self.workspace_slug}' not found on AnythingLLM server.")
                return []
            return workspaces[0].get("documents", [])
        except requests.RequestException as e:
            logger.warning(f"Unable to query existing workspace documents: {e}")
            return []

    def upload_and_embed(self, file_path: Path) -> Dict[str, Any]:
        """POST /v1/document/upload with addToWorkspaces=<slug>."""
        url = f"{self.api_base}/v1/document/upload"
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {"addToWorkspaces": self.workspace_slug}
            resp = requests.post(url, headers=self.headers, files=files, data=data, timeout=120)
        resp.raise_for_status()
        return resp.json()


def find_knowledge_files() -> List[Path]:
    """Scan knowledge_base/ for .pdf, .md, and .txt files, excluding README.md."""
    project_root = Path(__file__).parent.parent
    knowledge_dir = project_root / "knowledge_base"
    files: List[Path] = []
    if knowledge_dir.exists():
        for pattern in ("*.pdf", "*.md", "*.txt"):
            files.extend(knowledge_dir.glob(pattern))
    files = [f for f in files if f.name.upper() != "README.MD"]
    return sorted(files)


def seed_knowledge(base_url: str, api_key: str, workspace_slug: str) -> None:
    client = AnythingLLMClient(base_url, api_key, workspace_slug)

    logger.info(f"Connecting to AnythingLLM at {base_url} (workspace: {workspace_slug})...")
    existing_docs = client.get_workspace_documents()
    existing_titles = {d.get("title") for d in existing_docs if d.get("title")}
    logger.info(f"Found {len(existing_titles)} existing document(s) in workspace '{workspace_slug}'.")

    local_files = find_knowledge_files()
    logger.info(f"Found {len(local_files)} local knowledge base document(s) in knowledge_base/.")

    uploaded = skipped = failed = 0
    for file_path in local_files:
        if file_path.name in existing_titles:
            logger.info(f"  ⊘ Skipping {file_path.name} (already indexed)")
            skipped += 1
            continue

        logger.info(f"  ↗ Uploading & embedding {file_path.name}...")
        try:
            result = client.upload_and_embed(file_path)
            if result.get("success"):
                uploaded += 1
                logger.info(f"    ✓ {file_path.name} successfully indexed.")
            else:
                failed += 1
                logger.error(f"    ✗ {file_path.name} failed: {result.get('error')}")
        except requests.RequestException as e:
            failed += 1
            logger.error(f"    ✗ {file_path.name} error: {e}")

    logger.info("\n" + "=" * 50)
    logger.info(f"Knowledge Base Seeding Complete — Uploaded: {uploaded}, Skipped: {skipped}, Failed: {failed}")
    logger.info("=" * 50)


def main():
    if not Config.ANYTHINGLLM_API_KEY or Config.ANYTHINGLLM_API_KEY.startswith("paste-your"):
        logger.warning(
            "ANYTHINGLLM_API_KEY is not set or contains default placeholder in .env. "
            "Please configure ANYTHINGLLM_API_KEY to seed documents into AnythingLLM."
        )
        return

    seed_knowledge(Config.ANYTHINGLLM_BASE_URL, Config.ANYTHINGLLM_API_KEY, Config.ANYTHINGLLM_WORKSPACE)


if __name__ == "__main__":
    main()
