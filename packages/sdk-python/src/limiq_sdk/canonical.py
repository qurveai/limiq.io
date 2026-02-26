import json
from collections.abc import Mapping
from typing import Any


def canonicalize(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
