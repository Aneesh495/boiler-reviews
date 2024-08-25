"""WSGI entry point for the modular Boiler Reviews application."""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from boiler_reviews.web.app import create_app  # noqa: E402

app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
