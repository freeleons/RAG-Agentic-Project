# Knowledge Base Initialization Script Plan

Scope: Knowledge base auto-upload + one-click initialization only

## 📁 File Structure

```
scripts/
├── seed_knowledge.py            (NEW: Upload documents from knowledge_base/ to AnythingLLM)
└── seed_database.py             (NEW: One-click initialization: run migration + upload knowledge base)
```

---

## API Shape (Verified on running AnythingLLM container using built-in Swagger at `http://localhost:3001/api/docs/`)

Not guesses, verified against OpenAPI spec extracted from the real container's `/api/docs/swagger-ui-init.js`

| Purpose | Method + Path | Description |
|---|---|---|
| Upload file (and directly attach to workspace) | `POST /api/v1/document/upload` | `multipart/form-data`, field `file` (required) + `addToWorkspaces` (comma-separated workspace slug, one call completes both "upload" and "embed into workspace" without separately calling `update-embeddings`) |
| Query which documents already exist in workspace (for deduplication/skip) | `GET /api/v1/workspace/{slug}` | Returns `{"workspace": [{..., "documents": [...]}]}` (note array wrapper), use `documents[].title` to compare with local filenames |
| (Backup, not used in this plan) Manage embedding separately | `POST /api/v1/workspace/{slug}/update-embeddings` | Use this to attach when file is uploaded but not attached to a workspace |

Base URL = `ANYTHINGLLM_BASE_URL` + `/api` (consistent with verified chat endpoint prefix in `docs/anythingllm-setup.md`).

`POST /api/v1/document/upload` successful response example:
```json
{
  "success": true,
  "error": null,
  "documents": [
    {
      "location": "custom-documents/foo.txt-<uuid>.json",
      "name": "foo.txt-<uuid>.json",
      "title": "foo.txt",
      "docAuthor": "Unknown",
      "wordCount": 93,
      "token_count_estimate": 115
    }
  ]
}
```

`GET /api/v1/workspace/{slug}` successful response example:
```json
{
  "workspace": [
    {
      "id": 79,
      "name": "My workspace",
      "slug": "my-workspace-123",
      "documents": [],
      "threads": []
    }
  ]
}
```

---

## `scripts/seed_knowledge.py`

**Pseudocode:**
```python
#!/usr/bin/env python3
"""
Seed knowledge base documents to AnythingLLM.

This script:
1. Scans knowledge_base/ directory
2. Reads all .txt, .md, .pdf files
3. Uploads new files to AnythingLLM and embeds them into the target workspace
   in one call (POST /v1/document/upload with addToWorkspaces=<slug>)
4. Skips files whose original filename already appears in the workspace's
   document list

Usage:
    python -m scripts.seed_knowledge

Prerequisites:
    - AnythingLLM running at ANYTHINGLLM_BASE_URL (default: http://localhost:3001)
    - ANYTHINGLLM_API_KEY set in .env
    - ANYTHINGLLM_WORKSPACE set in .env (the workspace slug to embed into)
"""

import logging
import sys
from pathlib import Path
from typing import List, Dict, Any
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from server.config import Config  # values are Config class attrs, not module constants

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class AnythingLLMClient:
    """Thin client for the two AnythingLLM endpoints this script needs."""

    def __init__(self, base_url: str, api_key: str, workspace_slug: str):
        self.api_base = base_url.rstrip("/") + "/api"
        self.workspace_slug = workspace_slug
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def get_workspace_documents(self) -> List[Dict[str, Any]]:
        """GET /v1/workspace/{slug} -> workspace[0].documents[]"""
        url = f"{self.api_base}/v1/workspace/{self.workspace_slug}"
        resp = requests.get(url, headers=self.headers, timeout=10)
        resp.raise_for_status()
        workspaces = resp.json().get("workspace") or []
        if not workspaces:
            raise ValueError(f"workspace '{self.workspace_slug}' not found")
        return workspaces[0].get("documents", [])

    def upload_and_embed(self, file_path: Path) -> Dict[str, Any]:
        """POST /v1/document/upload with addToWorkspaces=<slug> — uploads AND
        embeds into the workspace in a single call."""
        url = f"{self.api_base}/v1/document/upload"
        with open(file_path, "rb") as f:
            files = {"file": (file_path.name, f)}
            data = {"addToWorkspaces": self.workspace_slug}
            resp = requests.post(url, headers=self.headers, files=files, data=data, timeout=120)
        resp.raise_for_status()
        return resp.json()


def find_knowledge_files() -> List[Path]:
    """Scan knowledge_base/ for .txt/.md/.pdf files, excluding README.md."""
    project_root = Path(__file__).parent.parent
    directories = [project_root / "knowledge_base"]
    files: List[Path] = []
    for directory in directories:
        if directory.exists():
            for pattern in ("*.txt", "*.md", "*.pdf"):
                files.extend(directory.glob(pattern))
    files = [f for f in files if f.name != "README.md"]
    return sorted(files)


def seed_knowledge(base_url: str, api_key: str, workspace_slug: str) -> None:
    client = AnythingLLMClient(base_url, api_key, workspace_slug)

    logger.info(f"Connecting to {base_url} (workspace: {workspace_slug})...")
    existing_docs = client.get_workspace_documents()
    existing_titles = {d.get("title") for d in existing_docs}
    logger.info(f"Found {len(existing_docs)} documents already in workspace")

    local_files = find_knowledge_files()
    logger.info(f"Found {len(local_files)} local files")

    uploaded = skipped = failed = 0
    for file_path in local_files:
        if file_path.name in existing_titles:
            logger.info(f"⊘ Skipping {file_path.name} (already indexed)")
            skipped += 1
            continue
        logger.info(f"Uploading {file_path.name}...")
        try:
            result = client.upload_and_embed(file_path)
            if result.get("success"):
                uploaded += 1
                logger.info(f"  ✓ {file_path.name} uploaded and embedded")
            else:
                failed += 1
                logger.error(f"  ✗ {file_path.name}: {result.get('error')}")
        except requests.RequestException as e:
            failed += 1
            logger.error(f"  ✗ {file_path.name}: {e}")

    logger.info(f"\nSummary — uploaded: {uploaded}, skipped: {skipped}, failed: {failed}")


def main():
    if not Config.ANYTHINGLLM_API_KEY or Config.ANYTHINGLLM_API_KEY.startswith("paste-your"):
        logger.error("ANYTHINGLLM_API_KEY not set in .env")
        sys.exit(1)
    seed_knowledge(Config.ANYTHINGLLM_BASE_URL, Config.ANYTHINGLLM_API_KEY, Config.ANYTHINGLLM_WORKSPACE)


if __name__ == "__main__":
    main()
```

**Note on Data Scope:**
- Scans `knowledge_base/` for active domain docs (`company_policies.txt`, `it_support_faq.txt`). Starter files from `tests/fixtures/sample-data/` are archived for test fixtures and omitted from vector ingestion.

---

## `scripts/seed_database.py`

**Pseudocode:**
```python
#!/usr/bin/env python3
"""
One-click initialization: run database migration + upload knowledge base documents.

Usage:
    python -m scripts.seed_database
"""

import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def seed_database():
    logger.info("Step 1: Running database migrations...")
    subprocess.run(
        ["flask", "--app", "server.app", "db", "upgrade"],
        check=True,
    )

    logger.info("Step 2: Seeding knowledge base...")
    from scripts.seed_knowledge import main as seed_knowledge_main
    seed_knowledge_main()

    logger.info("\n✓ Database seeding complete!")


if __name__ == "__main__":
    seed_database()
```




