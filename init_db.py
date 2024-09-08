"""Compatibility wrapper for the versioned migration command."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from boiler_reviews.db.migrate import main

if __name__ == "__main__":
    main_args = ["upgrade"]
    sys.argv[1:] = main_args
    main()
