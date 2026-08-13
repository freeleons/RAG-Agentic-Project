#!/usr/bin/env python3
"""
One-click initialization: run database migrations and upload knowledge base documents to AnythingLLM.

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
    logger.info("Step 1: Running Flask database migrations...")
    try:
        subprocess.run(
            [sys.executable, "-m", "flask", "--app", "server.app", "db", "upgrade"],
            check=True,
        )
        logger.info("✓ Database schema upgraded successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Database migration failed: {e}")
        sys.exit(1)

    logger.info("\nStep 2: Seeding knowledge base into AnythingLLM...")
    from scripts.seed_knowledge import main as seed_knowledge_main
    seed_knowledge_main()

    logger.info("\n✓ One-click database and knowledge base initialization complete!")


if __name__ == "__main__":
    seed_database()
