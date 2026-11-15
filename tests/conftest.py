"""Make desktop Windows modules and backend package importable to the test suite."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for source_root in (ROOT / "desktop" / "windows", ROOT / "backend"):
    source = str(source_root)
    if source not in sys.path:
        sys.path.insert(0, source)
