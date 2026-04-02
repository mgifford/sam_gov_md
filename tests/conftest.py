"""Shared pytest configuration and fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

# Add the scripts directory to sys.path so tests can import the modules directly.
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
