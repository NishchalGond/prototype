# CLI execution entrypoint for pipeline actions
import os
import sys
from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    port_env = os.environ.get("PORT", "8000")
    try:
        port = int(port_env)
    except (ValueError, TypeError):
        port = 8000

    # Apply schema migrations before the app accepts traffic. Previously the
    # schema came from create_all(), which creates missing tables but silently
    # ignores changed columns -- so a model change never reached production.
    # Set RUN_MIGRATIONS=0 to skip (e.g. if you run `alembic upgrade head` as a
    # separate deploy step).
    if os.environ.get("RUN_MIGRATIONS", "1") != "0":
        from backend.app.database.migrations import upgrade_to_head
        print("Applying database migrations...")
        upgrade_to_head()

    print(f"Starting server on 0.0.0.0:{port}...")
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port)
