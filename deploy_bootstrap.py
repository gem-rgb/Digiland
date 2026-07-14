from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / "Digiland" / "land_escrow"


def bootstrap() -> Path:
    """Load local environment files and expose the Django project on sys.path."""
    if not PROJECT_DIR.exists():
        raise RuntimeError(f"Expected Django project at {PROJECT_DIR}")

    for env_path in (
        ROOT_DIR / ".env",
        PROJECT_DIR / ".env",
        PROJECT_DIR / ".env.local",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    # Vercel environment: redirect SQLite to writable /tmp directory
    if os.environ.get("VERCEL") == "1":
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url or db_url.startswith("sqlite"):
            os.environ["DATABASE_URL"] = "sqlite:////tmp/db.sqlite3"

    project_path = str(PROJECT_DIR)
    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    return PROJECT_DIR
