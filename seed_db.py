"""Compatibility wrapper for the reproducible authored demo seed."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from boiler_reviews.cli import command_demo

if __name__ == "__main__":
    command_demo()
