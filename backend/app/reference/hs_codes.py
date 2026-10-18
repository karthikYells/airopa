"""The official HS 2022 code list (UN Comtrade reference file), for checking
and narrowing the model's product codes. A code that is not in this list does
not exist and is never used."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_PATH = Path(__file__).resolve().parent / "hs" / "hs2022.json"


@lru_cache(maxsize=1)
def _codes() -> dict[str, str]:
    return json.loads(_PATH.read_text(encoding="utf-8"))["codes"]


def label(code: str) -> str | None:
    return _codes().get(code)


def exists(code: str) -> bool:
    return code in _codes()


def children(heading: str) -> list[tuple[str, str]]:
    """The six-digit codes under a four-digit heading, with their official text."""
    return [(c, t) for c, t in _codes().items() if len(c) == 6 and c.startswith(heading)]
