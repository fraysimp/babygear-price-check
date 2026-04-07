"""Production WSGI entry point."""

import os
from pathlib import Path

# Set DB path from env or default
db_path = os.environ.get("DB_PATH", str(Path(__file__).parent / "data" / "babygear.db"))

from src.babygear_web.app import app

app.config["DB_PATH"] = db_path

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
