#!/usr/bin/env python3
"""Push resolved tickets into the AnythingLLM knowledge base.

Usage:
    python -m scripts.sync_resolved_tickets

Requires ANYTHINGLLM_BASE_URL / ANYTHINGLLM_API_KEY / ANYTHINGLLM_WORKSPACE
in .env (same config the agent's search_knowledge tool uses). Safe to re-run:
already-synced tickets (kb_synced_at set) are skipped.
"""
from server.app import create_app
from server.knowledge_sync import sync_resolved_tickets

if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        result = sync_resolved_tickets()
        print(
            f"Synced {result['synced']}/{result['total']} resolved tickets "
            f"to workspace '{app.config['ANYTHINGLLM_WORKSPACE']}' "
            f"({result['failed']} failed, will retry next run)."
        )
