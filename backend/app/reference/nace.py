"""EU industry codes (NACE Rev.2, A*64) as Eurostat publishes them, for naming
the industries a company sells to. A code not in this list is never used."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "nace_a64.json"


@lru_cache(maxsize=1)
def codes() -> dict[str, str]:
    return json.loads(_PATH.read_text(encoding="utf-8"))["codes"]
