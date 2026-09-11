"""Load a bounded PostgreSQL credential bundle without logging its payload."""

from __future__ import annotations

import json
import os
from typing import Mapping


def load_postgres_bundle(env_name: str, fields: Mapping[str, str | tuple[str, ...]]) -> None:
    raw = os.environ.get(env_name, "").strip()
    if not raw:
        return
    try:
        bundle = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{env_name} must contain a JSON object") from error
    if not isinstance(bundle, dict):
        raise ValueError(f"{env_name} must contain a JSON object")
    resolved = {}
    for target, sources in fields.items():
        names = (sources,) if isinstance(sources, str) else sources
        value = next((str(bundle.get(name, "")).strip() for name in names if str(bundle.get(name, "")).strip()), "")
        if value:
            resolved[target] = value
    missing = [target for target in fields if target not in resolved]
    if missing:
        raise ValueError(f"{env_name} is missing: {','.join(missing)}")
    for target, value in resolved.items():
        os.environ.setdefault(target, value)
